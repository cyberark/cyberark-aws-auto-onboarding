import aws_services

class log_mechanisem:
  def __init__(self):
    self.debug_mode = aws_services.get_params_from_param_store().debugMode
  def error_log_entry(self, message):
    if self.debug_mode == 'True':
      print('[ERROR] ' + message)
  def info_log_entry(self, message):
    if self.debug_mode == 'True':
      print('[INFO] ' + message)
    