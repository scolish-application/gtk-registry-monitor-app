import requests
from service.session import Session

SERVER_URL = "http://127.0.0.1:8080/api/registrations"

class RegistrationService:
    def get_entry_registrations(self, page=0, size=20):
        """
        Get registrations with ENTRY direction
        """
        try:
            response = requests.get(
                f"{SERVER_URL}",
                params={"direction": "ENTRY", "page": page, "size": size},
                cookies=Session.get_cookie()
            )
            
            if response.status_code == 200:
                return response.json()["content"]
            else:
                print(f"Error fetching registrations: {response.text}")
                return []
        except Exception as e:
            print(f"Exception in get_registrations: {str(e)}")
            return []
    
    def get_registration(self, registration_id):
        """
        Get a specific registration by ID
        """
        try:
            response = requests.get(
                f"{SERVER_URL}/{registration_id}",
                cookies=Session.get_cookie()
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching registration: {response.text}")
                return None
        except Exception as e:
            print(f"Exception in get_registration: {str(e)}")
            return None