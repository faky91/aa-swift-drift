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

from .models import DrifterWormhole
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
