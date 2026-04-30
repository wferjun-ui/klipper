class MotionDiagnostics:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.toolhead = None
        self.saved_x = {}
        self.default_speed = config.getfloat('travel_speed', 50., above=0.)

        self.printer.register_event_handler('klippy:ready', self._handle_ready)
        self.gcode.register_command('SAVE_X_POSITION', self.cmd_SAVE_X_POSITION,
                                    desc='Store current X position by name')
        self.gcode.register_command('RESTORE_X_POSITION', self.cmd_RESTORE_X_POSITION,
                                    desc='Move back to a saved X position')
        self.gcode.register_command('REPORT_STEPPER_SYNC', self.cmd_REPORT_STEPPER_SYNC,
                                    desc='Report commanded vs MCU step position')
        self.gcode.register_command('RUN_STEPPER_SPEED_TEST', self.cmd_RUN_STEPPER_SPEED_TEST,
                                    desc='Run a speed motion test and report step drift')

    def _handle_ready(self):
        self.toolhead = self.printer.lookup_object('toolhead')

    def _iter_steppers(self):
        kin = self.toolhead.get_kinematics()
        for s in kin.get_steppers():
            yield s

    def cmd_SAVE_X_POSITION(self, gcmd):
        name = gcmd.get('NAME', 'default')
        pos = self.toolhead.get_position()
        self.saved_x[name] = pos[0]
        gcmd.respond_info("Saved X position '%s' = %.3f" % (name, pos[0]))

    def cmd_RESTORE_X_POSITION(self, gcmd):
        name = gcmd.get('NAME', 'default')
        speed = gcmd.get_float('SPEED', self.default_speed, above=0.)
        if name not in self.saved_x:
            raise gcmd.error("Unknown saved X position '%s'" % (name,))
        pos = list(self.toolhead.get_position())
        pos[0] = self.saved_x[name]
        self.toolhead.manual_move(pos, speed)
        self.toolhead.wait_moves()
        gcmd.respond_info("Restored X position '%s'" % (name,))

    def _sync_report(self):
        lines = []
        for s in self._iter_steppers():
            s._query_mcu_position()
            cmd = s.get_commanded_position()
            mcu_steps = s.get_mcu_position()
            mcu_pos = s.mcu_to_commanded_position(mcu_steps)
            err = mcu_pos - cmd
            lines.append('%s cmd=%.5f mcu=%.5f err=%.5f step_dist=%.8f' % (
                s.get_name(), cmd, mcu_pos, err, s.get_step_dist()))
        return lines

    def cmd_REPORT_STEPPER_SYNC(self, gcmd):
        for l in self._sync_report():
            gcmd.respond_info(l)

    def cmd_RUN_STEPPER_SPEED_TEST(self, gcmd):
        axis = gcmd.get('AXIS', 'X').upper()
        dist = gcmd.get_float('DISTANCE', 50., above=0.)
        speed = gcmd.get_float('SPEED', 150., above=0.)
        cycles = gcmd.get_int('CYCLES', 5, minval=1)
        axis_map = {'X': 0, 'Y': 1, 'Z': 2, 'E': 3}
        if axis not in axis_map:
            raise gcmd.error('AXIS must be X, Y, Z, or E')
        ai = axis_map[axis]
        start = list(self.toolhead.get_position())
        before = self._sync_report()
        for _ in range(cycles):
            p1 = list(start)
            p1[ai] += dist
            self.toolhead.manual_move(p1, speed)
            self.toolhead.manual_move(start, speed)
        self.toolhead.wait_moves()
        after = self._sync_report()
        gcmd.respond_info('Before test:')
        for l in before:
            gcmd.respond_info(l)
        gcmd.respond_info('After test:')
        for l in after:
            gcmd.respond_info(l)


def load_config(config):
    return MotionDiagnostics(config)
