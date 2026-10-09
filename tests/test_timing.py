"""Clock-driven controller tests. No sleeps or real game input."""
import random
import unittest
import test_controller as fixtures
from test_controller import scene, advice


class TimingTests(unittest.TestCase):
    def bot(self, strength=100, rate=30):
        bot, keys = fixtures.ControllerTests().bot(rate, 0)
        bot.configure(rate, 0, strength)
        return bot, keys

    def test_think_deadline_survives_fresh_poses_and_advice(self):
        bot, keys = self.bot()
        state = scene()
        for i in range(47):
            now = .4 + i * .01
            state = {**state, 'start': dict(state['start'], y=-2 if i < 20 else -1)}
            bot.update(now, state, advice(state, ['L'], -1), now, True)
            if i < 46:
                self.assertFalse(keys)
        bot.update(.861, state, advice(state, ['L'], -1), .861, True)
        self.assertEqual(keys, [0x25])
        self.assertEqual(bot.timing_started, .4)

    def test_acknowledgement_runs_during_gap_and_zero_applies_live(self):
        bot, keys = self.bot()
        state = scene()
        for now in (.4, .861):
            bot.update(now, state, advice(state, ['L','L'], -2), now, True)
        moved = {**state, 'start': dict(state['start'], x=2)}
        bot.update(.885, moved, None, .885, True)
        self.assertIsNone(bot.waiting)
        bot.update(.90, moved, None, .90, True)
        self.assertEqual(bot.reason, 'Dynamic tempo')
        self.assertEqual(keys, [0x25])
        bot.configure(30, 0, 0)
        bot.update(.91, moved, None, .91, True)
        self.assertEqual(keys, [0x25, 0x25])

    def test_verified_alignment_drops_without_an_extra_tempo_gap(self):
        for rate in (2, 30):
            bot, keys = self.bot(rate=rate);state = scene()
            for now in (.4, .861):
                bot.update(now, state, advice(state, ['L'], -1), now, True)
            moved = {**state, 'start': dict(state['start'], x=2)}
            bot.update(.885, moved, None, .885, True)
            # A late deeper candidate must not redirect an already aligned piece.
            deeper = advice(moved, ['R'], 1);deeper['candidate']['lookahead'] = 6
            bot.update(.893, moved, deeper, .893, True)
            self.assertEqual(keys, [0x25, 0x20])
            self.assertFalse(bot.deep_replanned)

    def test_drop_still_requires_fresh_aligned_pixels_and_focus(self):
        for fault in ('next', 'stale', 'unfocused', 'shifted'):
            bot, keys = self.bot(strength=0);state = scene()
            bot.update(.4, state, advice(state, ['L'], -1), .4, True)
            moved = {**state, 'start': dict(state['start'], x=2)}
            bot.update(.425, moved, None, .425, True)
            if fault=='shifted':moved={**moved,'start':dict(moved['start'],x=1)}
            bot.update(.55, moved, None, .4 if fault=='stale' else .55,
                       fault!='unfocused', source='next' if fault=='next' else 'pixels')
            self.assertEqual(keys,[0x25],fault)

    def test_danger_and_recovery_cancel_thinking_without_removing_base_tempo(self):
        for danger in ('height', 'clearance', 'survive', 'retry'):
            bot, keys = self.bot()
            state = scene()
            bot.update(.4, state, advice(state), .4, True)
            if danger == 'height':state['board'][10][0] = 'G'
            if danger == 'clearance':state['start']['y'] = 15
            if danger == 'retry':bot.retries = 1
            result = advice(state)
            if danger == 'survive':result['candidate']['auto']['mode'] = 'survive'
            bot.update(.42, state, result, .42, True)
            self.assertEqual(keys, [0x20], danger)
        bot, keys = self.bot(rate=2)
        state = scene()
        bot.last_tap_at = .3
        result = advice(state);result['candidate']['auto']['mode'] = 'survive'
        bot.update(.4, state, result, .4, True)
        self.assertFalse(keys)
        bot.update(.81, state, result, .81, True)
        self.assertEqual(keys, [0x20])

    def test_hold_keeps_thought_and_verified_lock_starts_next_rhythm(self):
        bot, keys = self.bot()
        state = {**scene(), 'hold': 'O', 'allowHold': True}
        choice = advice(state);choice['candidate']['useHold'] = True
        for now in (.4, .861):bot.update(now, state, choice, now, True)
        self.assertEqual(keys, [0x10])
        held = {**state, 'piece': 'O', 'hold': 'T', 'start': dict(x=4,y=-2,r=0)}
        bot.update(.89, held, None, .89, True)
        self.assertIsNone(bot.waiting)
        bot.update(.92, held, advice(held), .92, True)
        self.assertEqual(bot.reason, 'Dynamic tempo')
        self.assertEqual(bot.timing_started, .4)
        bot.update(1.083, held, advice(held), 1.083, True)
        self.assertEqual(keys, [0x10, 0x20])
        next_state = {**scene(), 'piece': 'I', 'board': bot.waiting['board'], 'generation': 2, 'queue': ['O','S','J']}
        bot.update(1.12, next_state, None, 1.12, True)
        self.assertEqual(bot.placed, 1)
        bot.update(1.14, next_state, advice(next_state), 1.14, True)
        self.assertEqual(bot.reason, 'Thinking')
        self.assertEqual(keys, [0x10, 0x20])

    def test_pause_stale_pixels_and_stop_are_not_delayed(self):
        bot, keys = self.bot();state = scene()
        bot.update(.4, state, advice(state), .4, True)
        bot.update(.41, state, advice(state), .41, False)
        self.assertEqual(bot.phase, 'paused')
        bot.update(1., state, advice(state), .4, True)
        self.assertFalse(keys)
        self.assertTrue(bot.recovery)
        for now in (1.1,1.13,1.16,1.19):bot.update(now, state, advice(state), now, True)
        self.assertEqual(keys, [0x20])
        bot.stop();bot.update(2., state, advice(state), 2., True)
        self.assertEqual(keys, [0x20])

    def test_varied_bounded_intervals_and_monotonic_strength(self):
        gaps = []
        for strength in (25, 100):
            bot, keys = self.bot(strength)
            bot.rng = random.Random(19);state = scene()
            now = .4;previous = None;intervals = []
            for _ in range(400):
                if bot.pace_ready(now,state,advice(state)['candidate'],True):
                    bot.send('L',now) # mocked sink; exercise the clock, not movement
                    if previous is not None:intervals.append(now-previous)
                    previous = now
                now += .01
            self.assertGreater(len({round(v,2) for v in intervals}), 3)
            self.assertLess(max(intervals), .24)
            gaps.append(sum(intervals)/len(intervals))
        self.assertGreater(gaps[1], gaps[0]*2)


if __name__ == '__main__':unittest.main()
