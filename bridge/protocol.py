"""Pure command validation; independent of FreeCAD."""
import math

class CommandError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def validate_command(command, session, revision):
    if not isinstance(command, dict):
        raise CommandError('Expected a JSON object.')
    if command.get('session') != session:
        raise CommandError('The FreeCAD document session changed. Refresh and retry.', 409)
    if type(command.get('revision')) is not int or command['revision'] != revision:
        raise CommandError('The model changed in FreeCAD. Review the updated dimensions and retry.', 409)
    if command.get('operation') not in ('set_length', 'save'):
        raise CommandError('Unsupported operation.')
    request_id = command.get('requestId')
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
        raise CommandError('A request identifier is required.')
    if command['operation'] == 'set_length':
        value = command.get('lengthMm')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise CommandError('Length must be a finite number in millimeters.')
        if not 25.4 <= value <= 2438.4:
            raise CommandError('Prototype length must be between 1 and 96 inches.')
    return command
