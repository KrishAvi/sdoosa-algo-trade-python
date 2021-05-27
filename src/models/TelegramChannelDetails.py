class TelegramChannelDetails:
  #bot_token = None
  #channel_id = None
  def __init__(self):
    self.bot_token = None
    self.channel_id = None

  def setBottoken(self, bot_token):
    self.bot_token = bot_token

  def setChannelId(self, channel_id):
    self.channel_id = channel_id


