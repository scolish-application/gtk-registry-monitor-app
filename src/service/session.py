class Session:
    _cookie = {}

    @staticmethod
    def set_cookie(cookie_dict):
        Session._cookie = cookie_dict

    @staticmethod
    def get_cookie():
        return Session._cookie