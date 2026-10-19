"""کلاس پایه همه صرافی ها"""

class BaseExchange:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret

    def get_name(self):
        return self.__class__.__name__
