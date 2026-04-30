# Closed loop print control for extrusion flow compensation
#
# Copyright (C) 2026
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

MIN_DT = 0.001


class PIDFeedForwardHybridController:
    def __init__(self, config):
        self.kp = config.getfloat('flow_kp', 0.10, minval=0.)
        self.ki = config.getfloat('flow_ki', 0.02, minval=0.)
        self.kd = config.getfloat('flow_kd', 0.0, minval=0.)
        self.kff = config.getfloat('flow_kff', 1.0, minval=0.)
        self.integrator_limit = config.getfloat('integrator_limit', 1.0,
                                                above=0.)
        self.max_correction = config.getfloat('max_correction', 0.25,
                                              minval=0.0)
        self.max_slew_rate = config.getfloat('max_slew_rate', 5.0, above=0.)
        self.integral = 0.
        self.last_error = 0.
        self.last_output = 0.

    def update(self, expected_flow, real_flow, dt):
        dt = max(dt, MIN_DT)
        error = expected_flow - real_flow
        self.integral += error * dt
        self.integral = max(-self.integrator_limit,
                            min(self.integrator_limit, self.integral))
        derivative = (error - self.last_error) / dt

        pid = self.kp * error + self.ki * self.integral + self.kd * derivative
        ff = self.kff * expected_flow
        raw_output = ff + pid

        min_out = 1. - self.max_correction
        max_out = 1. + self.max_correction
        output = max(min_out, min(max_out, raw_output))

        max_delta = self.max_slew_rate * dt
        lower = self.last_output - max_delta
        upper = self.last_output + max_delta
        output = max(lower, min(upper, output))

        self.last_error = error
        self.last_output = output
        return output, error


class SensorFusionModule:
    def __init__(self, config):
        self.encoder_weight = config.getfloat('encoder_weight', 0.60, minval=0.)
        self.load_cell_weight = config.getfloat('load_cell_weight', 0.30,
                                                minval=0.)
        self.optical_weight = config.getfloat('optical_weight', 0.10, minval=0.)
        self.camera_weight = config.getfloat('camera_weight', 0.0, minval=0.)

    def fuse_flow(self, sensor_data):
        weighted_sum = 0.
        total_weight = 0.
        for key, weight in [
            ('encoder_flow', self.encoder_weight),
            ('load_cell_flow', self.load_cell_weight),
            ('optical_flow', self.optical_weight),
            ('camera_flow', self.camera_weight),
        ]:
            value = sensor_data.get(key)
            if value is None:
                continue
            weighted_sum += value * weight
            total_weight += weight

        if total_weight <= 0.:
            return None
        return weighted_sum / total_weight


class ClosedLoopExtrusionController:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')

        self.control_period = config.getfloat('control_period', 0.02,
                                              minval=0.001, maxval=0.02)
        self.safe_fallback_scale = config.getfloat('safe_fallback_scale', 1.0,
                                                   minval=0.0)
        self.sensor_timeout = config.getfloat('sensor_timeout', 0.1, above=0.)

        self.controller = PIDFeedForwardHybridController(config)
        self.fusion = SensorFusionModule(config)

        self.enabled = False
        self.fallback_active = False
        self.last_sensor_update = 0.
        self.last_control_time = None
        self.last_expected_flow = 0.
        self.last_real_flow = 0.
        self.last_error = 0.
        self.last_correction = 1.0
        self.sensor_data = {}

        self.gcode.register_mux_command(
            'SET_CLPC', 'MODE', 'ENABLE', self.cmd_SET_CLPC,
            desc=self.cmd_SET_CLPC_help)
        self.gcode.register_mux_command(
            'SET_CLPC', 'MODE', 'DISABLE', self.cmd_SET_CLPC,
            desc=self.cmd_SET_CLPC_help)
        self.gcode.register_command('CLPC_SENSOR_UPDATE',
                                    self.cmd_CLPC_SENSOR_UPDATE)
        self.gcode.register_command('CLPC_STATUS', self.cmd_CLPC_STATUS)

        self.timer = self.reactor.register_timer(self._control_loop,
                                                 self.reactor.NEVER)

    cmd_SET_CLPC_help = 'Enable or disable ClosedLoopPrintControl'
    def cmd_SET_CLPC(self, gcmd):
        mode = gcmd.get('MODE').upper()
        if mode == 'ENABLE':
            self.enabled = True
            self.fallback_active = False
            self.last_control_time = None
            self.reactor.update_timer(self.timer, self.reactor.NOW)
        else:
            self.enabled = False
            self.reactor.update_timer(self.timer, self.reactor.NEVER)
            self._apply_correction(1.0)

    def cmd_CLPC_SENSOR_UPDATE(self, gcmd):
        for key in ['ENCODER', 'LOAD_CELL', 'OPTICAL', 'CAMERA']:
            value = gcmd.get_float(key, None)
            if value is not None:
                self.sensor_data[key.lower() + '_flow'] = value
        expected = gcmd.get_float('EXPECTED', None)
        if expected is not None:
            self.last_expected_flow = max(0., expected)
        self.last_sensor_update = self.reactor.monotonic()

    def cmd_CLPC_STATUS(self, gcmd):
        gcmd.respond_info(
            'CLPC enabled=%s fallback=%s expected=%.6f real=%.6f '
            'error=%.6f correction=%.6f' % (
                self.enabled, self.fallback_active, self.last_expected_flow,
                self.last_real_flow, self.last_error, self.last_correction))

    def _control_loop(self, eventtime):
        if not self.enabled:
            return self.reactor.NEVER

        if self.last_control_time is None:
            dt = self.control_period
        else:
            dt = max(MIN_DT, eventtime - self.last_control_time)
        self.last_control_time = eventtime

        if eventtime - self.last_sensor_update > self.sensor_timeout:
            if not self.fallback_active:
                logging.warning('CLPC sensor timeout; entering safe fallback')
            self.fallback_active = True
            self.last_error = 0.
            self.last_correction = self.safe_fallback_scale
            self._apply_correction(self.safe_fallback_scale)
            return eventtime + self.control_period

        self.fallback_active = False
        real_flow = self.fusion.fuse_flow(self.sensor_data)
        if real_flow is None:
            self.last_error = 0.
            self.last_correction = self.safe_fallback_scale
            self._apply_correction(self.safe_fallback_scale)
            return eventtime + self.control_period

        self.last_real_flow = max(0., real_flow)
        correction, error = self.controller.update(self.last_expected_flow,
                                                   self.last_real_flow, dt)
        self.last_error = error
        self.last_correction = correction
        self._apply_correction(correction)
        return eventtime + self.control_period

    def _apply_correction(self, correction):
        # Hook point: integrators can override this module to bind correction
        # with a hardware-specific extrusion flow multiplier.
        pass


def load_config(config):
    return ClosedLoopExtrusionController(config)
