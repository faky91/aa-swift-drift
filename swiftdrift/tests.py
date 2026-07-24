"""
Automated tests of the app.

Run them (inside the venv of the Auth installation):

    python manage.py test swiftdrift

The tests build a small fake map (6 systems, 4 stargates) and use it
to verify the three core functions:

1. Expiry logic (16h default, 4h after EOL)
2. Celery task that deletes expired entries
3. Route calculation with and without drifter shortcuts
"""

import datetime

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from eve_sde.models import Constellation, Region, SolarSystem, Stargate

from .importer import parse_jump_bridges
from .models import DrifterWormhole, JumpBridge, WormholeStatusReport
from .routing import GRAPH_CACHE_KEY, find_route
from .tasks import delete_expired_wormholes


class SwiftDriftTestBase(TestCase):
    """Creates a mini map: chain A-B-C-D and a separate pair X-Y."""

    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(id=1, name="TestRegion")
        constellation = Constellation.objects.create(
            id=1, name="TestCon", region=region
        )

        def make_system(offset, name):
            return SolarSystem.objects.create(
                id=30000000 + offset,
                name=name,
                constellation=constellation,
                security_status=0.5,
            )

        cls.a = make_system(1, "Alpha")
        cls.b = make_system(2, "Bravo")
        cls.c = make_system(3, "Charlie")
        cls.d = make_system(4, "Delta")
        cls.x = make_system(5, "Xray")
        cls.y = make_system(6, "Yankee")

        # One stargate per connection is enough for the adjacency list,
        # the graph builder treats every pair as bidirectional
        gate_id = 0
        for system, destination in [
            (cls.a, cls.b),
            (cls.b, cls.c),
            (cls.c, cls.d),
            (cls.x, cls.y),
        ]:
            gate_id += 1
            Stargate.objects.create(
                id=gate_id,
                name=f"gate-{gate_id}",
                solar_system=system,
                destination=destination,
            )

        cls.user = User.objects.create(username="tester")

    def setUp(self):
        # The stargate graph is cached; clear it before every test so
        # tests cannot influence each other
        cache.delete(GRAPH_CACHE_KEY)


class ExpiryTests(SwiftDriftTestBase):
    """Tests for the automatic expiry logic."""

    def test_fresh_wormhole_expires_after_default_lifetime(self):
        wormhole = DrifterWormhole(
            system=self.b, hive="conflux", created_by=self.user
        )
        wormhole.save()
        remaining = wormhole.expires_at - timezone.now()
        # Default lifetime: 16 hours (small tolerance for runtime)
        self.assertAlmostEqual(remaining.total_seconds() / 3600, 16, delta=0.1)

    def test_eol_shortens_lifetime_to_four_hours(self):
        wormhole = DrifterWormhole(
            system=self.b, hive="conflux", created_by=self.user
        )
        wormhole.save()
        wormhole.eol = True
        wormhole.save()
        remaining = wormhole.expires_at - timezone.now()
        self.assertAlmostEqual(remaining.total_seconds() / 3600, 4, delta=0.1)

    def test_freshness_of_new_wormhole_is_high(self):
        wormhole = DrifterWormhole(
            system=self.b, hive="conflux", created_by=self.user
        )
        wormhole.save()
        self.assertGreaterEqual(wormhole.freshness_percent, 99)

    def test_freshness_of_expired_wormhole_is_zero(self):
        wormhole = DrifterWormhole(
            system=self.b, hive="conflux", created_by=self.user
        )
        wormhole.save()
        DrifterWormhole.objects.filter(pk=wormhole.pk).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1)
        )
        wormhole.refresh_from_db()
        self.assertEqual(wormhole.freshness_percent, 0)

    def test_task_deletes_expired_entries(self):
        wormhole = DrifterWormhole(
            system=self.b, hive="conflux", created_by=self.user
        )
        wormhole.save()
        # Artificially move the expiry date into the past
        DrifterWormhole.objects.filter(pk=wormhole.pk).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1)
        )
        deleted = delete_expired_wormholes()
        self.assertEqual(deleted, 1)
        self.assertEqual(DrifterWormhole.active().count(), 0)


class RoutingTests(SwiftDriftTestBase):
    """Tests for the route calculation."""

    def test_gate_route(self):
        # A-B-C-D is a chain: 3 jumps
        route = find_route(self.a.id, self.d.id, use_drifters=False)
        names = [step["system"].name for step in route]
        self.assertEqual(names, ["Alpha", "Bravo", "Charlie", "Delta"])

    def test_no_route_between_islands_without_drifters(self):
        # X/Y are not connected to the rest of the map
        route = find_route(self.a.id, self.y.id, use_drifters=False)
        self.assertIsNone(route)

    def test_drifter_shortcut_connects_islands(self):
        # A Conflux wormhole in B and in X connects the two islands
        DrifterWormhole(
            system=self.b, hive="conflux", bookmark="CFX in Bravo", created_by=self.user
        ).save()
        DrifterWormhole(
            system=self.x, hive="conflux", bookmark="CFX in Xray", created_by=self.user
        ).save()

        route = find_route(self.a.id, self.y.id, use_drifters=True)
        steps = [(step["system"].name, step["via"]) for step in route]
        self.assertEqual(
            steps,
            [
                ("Alpha", "start"),
                ("Bravo", "gate"),
                ("Xray", "drifter"),
                ("Yankee", "gate"),
            ],
        )

        # The entry annotation must sit on Bravo (the system BEFORE the
        # drifter step) and carry the bookmark of the entry wormhole
        bravo = route[1]
        self.assertEqual(bravo["enter_hive"], "conflux")
        self.assertEqual(bravo["enter_bookmark"], "CFX in Bravo")

        # The arrival step carries the bookmark of the exit wormhole
        xray = route[2]
        self.assertEqual(xray["exit_bookmark"], "CFX in Xray")

    def test_different_hives_are_not_connected(self):
        # Conflux in B, Barbican in X: NO connection, different hives
        DrifterWormhole(system=self.b, hive="conflux", created_by=self.user).save()
        DrifterWormhole(system=self.x, hive="barbican", created_by=self.user).save()

        route = find_route(self.a.id, self.y.id, use_drifters=True)
        self.assertIsNone(route)

    def test_jump_bridge_connects_islands(self):
        # A jump bridge between C and X connects the two islands
        JumpBridge.objects.create(
            from_system=self.c, to_system=self.x, created_by=self.user
        )

        route = find_route(self.a.id, self.y.id, use_drifters=False)
        steps = [(step["system"].name, step["via"]) for step in route]
        self.assertEqual(
            steps,
            [
                ("Alpha", "start"),
                ("Bravo", "gate"),
                ("Charlie", "gate"),
                ("Xray", "bridge"),
                ("Yankee", "gate"),
            ],
        )

    def test_bridges_can_be_disabled(self):
        JumpBridge.objects.create(
            from_system=self.c, to_system=self.x, created_by=self.user
        )
        route = find_route(
            self.a.id, self.y.id, use_drifters=False, use_bridges=False
        )
        self.assertIsNone(route)


class ImporterTests(SwiftDriftTestBase):
    """Tests for the bridge list parser."""

    def test_corptools_format_with_structure_id(self):
        text = "1045899402916 Alpha --> Bravo"
        entries, errors = parse_jump_bridges(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["structure_id"], 1045899402916)
        self.assertEqual(entry["from_system"].name, "Alpha")
        self.assertEqual(entry["to_system"].name, "Bravo")

    def test_format_without_structure_id(self):
        entries, errors = parse_jump_bridges("Alpha \u00bb Bravo - Papa Bridge")
        self.assertEqual(errors, [])
        self.assertIsNone(entries[0]["structure_id"])

    def test_unknown_system_is_reported(self):
        entries, errors = parse_jump_bridges("1045899402916 Nowhere --> Bravo")
        self.assertEqual(entries, [])
        self.assertEqual(len(errors), 1)


class NormalWormholeTests(SwiftDriftTestBase):
    """Normal wormholes are direct A-B edges with optional lifetime."""

    def test_normal_wormhole_connects_two_systems(self):
        DrifterWormhole.objects.create(
            system=self.c,
            destination_system=self.x,
            hive="normal",
            created_by=self.user,
        )
        route = find_route(self.a.id, self.y.id, use_bridges=False)
        steps = [(step["system"].name, step["via"]) for step in route]
        self.assertEqual(
            steps,
            [
                ("Alpha", "start"),
                ("Bravo", "gate"),
                ("Charlie", "gate"),
                ("Xray", "drifter"),
                ("Yankee", "gate"),
            ],
        )

    def test_normal_wormhole_lifetime_override(self):
        wormhole = DrifterWormhole.objects.create(
            system=self.c,
            destination_system=self.x,
            hive="normal",
            lifetime_hours=48,
            created_by=self.user,
        )
        lifetime = wormhole.expires_at - wormhole.created_at
        self.assertEqual(round(lifetime.total_seconds() / 3600), 48)

    def test_exclusion_avoids_the_wormhole(self):
        wormhole = DrifterWormhole.objects.create(
            system=self.c,
            destination_system=self.x,
            hive="normal",
            created_by=self.user,
        )
        route = find_route(
            self.a.id,
            self.y.id,
            use_bridges=False,
            exclude_wormhole_ids=[wormhole.id],
        )
        self.assertIsNone(route)


class StatusReportTests(SwiftDriftTestBase):
    """Pilot votes: one changeable vote per user, counted per hour."""

    def test_one_vote_per_user_is_updated_not_duplicated(self):
        wormhole = DrifterWormhole.objects.create(
            system=self.b, hive="conflux", created_by=self.user
        )
        WormholeStatusReport.objects.update_or_create(
            wormhole=wormhole, user=self.user, defaults={"is_up": True}
        )
        WormholeStatusReport.objects.update_or_create(
            wormhole=wormhole, user=self.user, defaults={"is_up": False}
        )
        reports = WormholeStatusReport.objects.filter(wormhole=wormhole)
        self.assertEqual(reports.count(), 1)
        self.assertFalse(reports.first().is_up)

    def test_reports_are_deleted_with_the_wormhole(self):
        wormhole = DrifterWormhole.objects.create(
            system=self.b, hive="conflux", created_by=self.user
        )
        WormholeStatusReport.objects.create(
            wormhole=wormhole, user=self.user, is_up=False
        )
        wormhole.delete()
        self.assertEqual(WormholeStatusReport.objects.count(), 0)


class WhTypeCatalogTests(SwiftDriftTestBase):
    """Sanity of the bundled type catalog and the form auto-fill."""

    def test_catalog_values(self):
        from . import wh_types

        self.assertGreaterEqual(len(wh_types.WH_TYPES), 90)
        self.assertEqual(wh_types.lifetime_for("B274"), 24)
        self.assertEqual(wh_types.size_for("B274"), "l")
        self.assertEqual(wh_types.size_for("E004"), "s")
        self.assertIsNone(wh_types.lifetime_for("K162"))

    def test_form_autofills_from_type_code(self):
        from .forms import WormholeForm

        form = WormholeForm(
            data={
                "system_name": "Alpha",
                "hive": "normal",
                "wh_type": "b274",
                "destination_name": "Bravo",
                "mass_status": "fresh",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["wh_type"], "B274")
        self.assertEqual(form.cleaned_data["size"], "l")
        self.assertEqual(form.cleaned_data["lifetime_hours"], 24)

    def test_manual_lifetime_overrides_catalog(self):
        from .forms import WormholeForm

        form = WormholeForm(
            data={
                "system_name": "Alpha",
                "hive": "normal",
                "wh_type": "B274",
                "destination_name": "Bravo",
                "lifetime_hours": "6",
                "mass_status": "fresh",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["lifetime_hours"], 6)


class JSpaceRoutingTests(SwiftDriftTestBase):
    """Normal wormholes may lead to J-space; the route can end there."""

    def test_route_to_jspace_destination(self):
        jsystem = SolarSystem.objects.create(
            id=31000001,
            name="J100001",
            constellation=self.a.constellation,
            security_status=-1.0,
        )
        DrifterWormhole.objects.create(
            system=self.c,
            destination_system=jsystem,
            hive="normal",
            wh_type_code="B274",
            created_by=self.user,
        )
        route = find_route(self.a.id, jsystem.id, use_bridges=False)
        self.assertIsNotNone(route)
        self.assertEqual(route[-1]["system"].name, "J100001")
        self.assertEqual(route[-1]["via"], "drifter")
