import requests
from service.session import Session

SERVER_URL = "http://127.0.0.1:8080/api/authentication"

class AuthService:
    @staticmethod
    def login(username: str, password: str):
        try:
            response = requests.post(
                f"{SERVER_URL}/login",
                json={"username": username, "password": password}
            )

            if response.status_code == 200:
                Session.set_cookie(response.cookies.get_dict())
                return True, "Login realizado com sucesso."
            else:
                return False, response.text
        except Exception as e:
            return False, str(e)