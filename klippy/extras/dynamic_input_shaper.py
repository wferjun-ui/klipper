# Dynamic input shaper adaptation using accelerometer feedback
#
# Copyright (C) 2026
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import collections
import logging
import math


class DynamicInputShaper:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')
        self.input_shaper = None
        self.enabled = config.getboolean('enabled', False)
        self.sample_rate_hz = config.getint('sample_rate', 800, minval=500)
        self.window_seconds = config.getfloat('window_seconds', 1.0,
                                              minval=0.5, maxval=2.0)
        self.ema_alpha = config.getfloat('ema_alpha', 0.2, minval=0.01,
                                         maxval=1.0)
        self.update_interval = config.getfloat('update_interval', 0.5,
                                               minval=0.1)
        self.freq_min_hz = config.getfloat('freq_min_hz', 10.0, minval=1.0)
        self.freq_max_hz = config.getfloat('freq_max_hz', 200.0, minval=2.0)
        self.freq_step_hz = config.getfloat('freq_step_hz', 1.0, minval=0.5)
        self.signal_timeout = config.getfloat('signal_timeout', 2.0, minval=0.5)
        self.static_fallback = config.getboolean('static_fallback', True)
        self.chip_name = config.get('accelerometer_chip', 'adxl345')
        self.shaper_type = config.get('shaper_type', 'mzv')
        self.dynamic_states = {
            'x': {'ema_freq': None, 'last_freq': None},
            'y': {'ema_freq': None, 'last_freq': None},
        }
        self.last_update_time = 0.
        self.bg_client = None
        self.timer = None

        self.printer.register_event_handler('klippy:connect', self._handle_connect)
        self.gcode.register_command('SET_DYNAMIC_INPUT_SHAPER',
                                    self.cmd_SET_DYNAMIC_INPUT_SHAPER,
                                    desc=self.cmd_SET_DYNAMIC_INPUT_SHAPER_help)

    def _handle_connect(self):
        self.input_shaper = self.printer.lookup_object('input_shaper', None)
        if self.input_shaper is None:
            raise self.printer.config_error(
                "[dynamic_input_shaper] requires [input_shaper]")
        self.timer = self.reactor.register_timer(self._timer_event)
        if self.enabled:
            self._start_streaming()
            self.reactor.update_timer(self.timer, self.reactor.NOW)

    def _start_streaming(self):
        if self.bg_client is not None:
            return
        accel = self.printer.lookup_object(self.chip_name, None)
        if accel is None:
            raise self.printer.command_error(
                "Accelerometer chip '%s' not found" % (self.chip_name,))
        self.bg_client = accel.start_internal_client()

    def _stop_streaming(self):
        if self.bg_client is None:
            return
        self.bg_client.finish_measurements()
        self.bg_client = None

    def update_resonance_profile(self, axis, samples):
        if not samples:
            return None
        if axis == 'x':
            values = [s[1] for s in samples]
        else:
            values = [s[2] for s in samples]
        mean = sum(values) / float(len(values))
        values = [v - mean for v in values]
        if not values:
            return None
        peak_freq = self._estimate_peak_frequency(values, self.sample_rate_hz)
        if peak_freq is None:
            return None
        state = self.dynamic_states[axis]
        if state['ema_freq'] is None:
            state['ema_freq'] = peak_freq
        else:
            state['ema_freq'] = (self.ema_alpha * peak_freq
                                 + (1. - self.ema_alpha) * state['ema_freq'])
        state['last_freq'] = peak_freq
        return state['ema_freq']

    def _estimate_peak_frequency(self, values, sample_rate_hz):
        if len(values) < 64:
            return None
        best_freq = None
        best_power = 0.
        freq = self.freq_min_hz
        while freq <= self.freq_max_hz:
            power = self._goertzel_power(values, sample_rate_hz, freq)
            if power > best_power:
                best_power = power
                best_freq = freq
            freq += self.freq_step_hz
        return best_freq

    def _goertzel_power(self, values, sample_rate_hz, freq_hz):
        omega = 2.0 * math.pi * freq_hz / sample_rate_hz
        coeff = 2.0 * math.cos(omega)
        s_prev = s_prev2 = 0.0
        for sample in values:
            s = sample + coeff * s_prev - s_prev2
            s_prev2, s_prev = s_prev, s
        return s_prev2 * s_prev2 + s_prev * s_prev - coeff * s_prev * s_prev2

    def apply_dynamic_filter(self, axis_freqs):
        cmd = ["SET_INPUT_SHAPER SHAPER_TYPE=%s" % (self.shaper_type,)]
        for axis, freq in axis_freqs.items():
            if freq is None:
                continue
            cmd.append("SHAPER_FREQ_%s=%.3f" % (axis.upper(), freq))
        if len(cmd) == 1:
            return
        self.gcode.run_script_from_command(' '.join(cmd))

    def _timer_event(self, eventtime):
        if not self.enabled:
            return self.reactor.NEVER
        if self.bg_client is None:
            self._start_streaming()
        samples = self.bg_client.get_samples()
        if not samples:
            if self.static_fallback and (eventtime - self.last_update_time
                                         > self.signal_timeout):
                logging.warning("DynamicInputShaper signal timeout, static fallback active")
            return eventtime + self.update_interval
        window_samples = int(self.window_seconds * self.sample_rate_hz)
        samples = samples[-window_samples:]
        axis_freqs = {}
        for axis in ('x', 'y'):
            axis_freqs[axis] = self.update_resonance_profile(axis, samples)
        self.apply_dynamic_filter(axis_freqs)
        self.last_update_time = eventtime
        return eventtime + self.update_interval

    cmd_SET_DYNAMIC_INPUT_SHAPER_help = "Enable/disable dynamic input shaper"
    def cmd_SET_DYNAMIC_INPUT_SHAPER(self, gcmd):
        enable = gcmd.get_int('ENABLE', None, minval=0, maxval=1)
        if enable is not None:
            self.enabled = bool(enable)
            if self.enabled:
                self._start_streaming()
                self.reactor.update_timer(self.timer, self.reactor.NOW)
            else:
                self._stop_streaming()
                self.reactor.update_timer(self.timer, self.reactor.NEVER)
        stats = collections.OrderedDict([
            ('enabled', int(self.enabled)),
            ('chip', self.chip_name),
            ('sample_rate', self.sample_rate_hz),
            ('window_seconds', self.window_seconds),
            ('x_freq', self.dynamic_states['x']['ema_freq']),
            ('y_freq', self.dynamic_states['y']['ema_freq']),
        ])
        gcmd.respond_info(' '.join(['%s=%s' % (k, v) for k, v in stats.items()]))


def load_config(config):
    return DynamicInputShaper(config)
