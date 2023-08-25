from fake_useragent import UserAgent
import requests

def get_html(url:str) -> (str):
    try:
        ua = UserAgent()
        headers = {'User-Agent': ua.random}
        result = ''
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Page unavailable: {response.status_code} for {url}")
    except Exception as e:
        raise Exception(f"Page unavailable: {str(e)} for {url}")