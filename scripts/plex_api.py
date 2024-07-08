
def plex_refresh(media_folder_srv, plex_url, x_plex_token):
    from os import system
    system(rf'curl --insecure -G --data-urlencode "path={media_folder_srv}" {plex_url}/library/sections/1/refresh?X-Plex-Token={x_plex_token}')
