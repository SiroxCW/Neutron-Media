
def jelly_user(username, password, jelly_url, jelly_key):
    from requests import post
    endpoint_url = f"{jelly_url}/Users/New"

    headers = {
        'X-Emby-Token': jelly_key,
        'Content-Type': 'application/json'
    }

    payload = {
        'Name': username,
        'Password': password,
        'IsAdministrator': False
    }

    # Post requests to create new user
    response = post(endpoint_url, json=payload, headers=headers)

    return response.status_code

def jelly_refresh(jelly_url, jelly_key):
    from requests import post
    endpoint_url = f"{jelly_url}/Library/Refresh"

    headers = {
        'X-Emby-Token': jelly_key,
    }

    # Post requests to refresh library
    response = post(endpoint_url, headers=headers)

    return response.status_code
