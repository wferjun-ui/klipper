import os, json, logging

class PowerLossRecovery:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.reactor = self.printer.get_reactor()
        self.vsd = None
        self.state_file = os.path.expanduser(config.get(
            'state_file', '~/printer_data/config/powerloss_recovery.json'))
        self.save_interval = config.getint('save_interval', 5, minval=1)
        self._next_save = 0.
        self._last_saved_pos = -1
        self._recovered_state = None

        self.printer.register_event_handler('klippy:ready', self._handle_ready)
        self.gcode.register_command('POWERLOSS_SAVE_STATE',
                                    self.cmd_POWERLOSS_SAVE_STATE,
                                    desc='Save print state for power-loss recovery')
        self.gcode.register_command('POWERLOSS_RECOVER_PRINT',
                                    self.cmd_POWERLOSS_RECOVER_PRINT,
                                    desc='Resume the last interrupted SD print')
        self.gcode.register_command('POWERLOSS_CLEAR_STATE',
                                    self.cmd_POWERLOSS_CLEAR_STATE,
                                    desc='Clear saved power-loss recovery state')

    def _handle_ready(self):
        self.vsd = self.printer.lookup_object('virtual_sdcard', None)
        if self.vsd is None:
            logging.info('powerloss_recovery disabled: virtual_sdcard not found')
            return
        self.printer.register_event_handler('toolhead:sync_print_time',
                                            self._handle_sync_print_time)
        self.printer.register_event_handler('virtual_sdcard:reset_file',
                                            self._clear_state)
        self._recovered_state = self._load_state()

    def _handle_sync_print_time(self, curtime, print_time, est_print_time):
        if self.vsd is None or not self.vsd.is_active():
            return
        if curtime < self._next_save:
            return
        self._next_save = curtime + self.save_interval
        self._save_state()

    def _read_position(self):
        gmove = self.printer.lookup_object('gcode_move')
        gpos = gmove.get_status(self.reactor.monotonic())['gcode_position']
        return {'x': gpos.x, 'y': gpos.y, 'z': gpos.z, 'e': gpos.e}

    def _save_state(self):
        if self.vsd is None or self.vsd.current_file is None:
            return
        file_position = self.vsd.get_file_position()
        if file_position == self._last_saved_pos:
            return
        state = {
            'path': os.path.basename(self.vsd.file_path() or ''),
            'file_position': file_position,
            'file_size': self.vsd.file_size,
            'position': self._read_position(),
        }
        self._write_state(state)
        self._last_saved_pos = file_position

    def _write_state(self, state):
        dname = os.path.dirname(self.state_file)
        if dname:
            os.makedirs(dname, exist_ok=True)
        tmp_name = self.state_file + '.tmp'
        with open(tmp_name, 'w') as f:
            json.dump(state, f)
        os.replace(tmp_name, self.state_file)

    def _load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _clear_state(self, *args):
        self._last_saved_pos = -1
        self._recovered_state = None
        try:
            os.remove(self.state_file)
        except OSError:
            pass

    def cmd_POWERLOSS_SAVE_STATE(self, gcmd):
        self._save_state()
        gcmd.respond_info('Power-loss state saved')

    def cmd_POWERLOSS_CLEAR_STATE(self, gcmd):
        self._clear_state()
        gcmd.respond_info('Power-loss state cleared')

    def cmd_POWERLOSS_RECOVER_PRINT(self, gcmd):
        state = self._load_state()
        if state is None:
            raise gcmd.error('No saved power-loss state found')
        if self.vsd is None:
            raise gcmd.error('virtual_sdcard not configured')
        if self.vsd.is_active():
            raise gcmd.error('Printer is busy')
        fname = state.get('path')
        file_pos = int(state.get('file_position', 0))
        if not fname:
            raise gcmd.error('Saved state missing file path')
        self.gcode.run_script_from_command('SDCARD_PRINT_FILE FILENAME=%s' % (fname,))
        self.gcode.run_script_from_command('M25')
        self.gcode.run_script_from_command('M26 S=%d' % (max(0, file_pos),))
        self.gcode.run_script_from_command('M24')
        pos = state.get('position', {})
        gcmd.respond_info('Recovery started at byte %d for %s (last xyz=(%.3f, %.3f, %.3f))'
                          % (file_pos, fname,
                             float(pos.get('x', 0.)),
                             float(pos.get('y', 0.)),
                             float(pos.get('z', 0.))))


def load_config(config):
    return PowerLossRecovery(config)
