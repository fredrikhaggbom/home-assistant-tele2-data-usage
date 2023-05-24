# home-assistant-tele2-data-usage

Note: This component is a work in progress


Custom component (sensor) for Home-assistant that fetches mobile data left from Tele2


Yaml config example (no UI config flow yet):

````
sensor:
  - platform: tele2_datausage
    name: "Tele2 Data Usage"  #UI name of component
    username: "username"      #My TSO username
    passwordf: "password"     #My TSO password
    poll_interval: 1800       #How often data should be refreshed (in seconds)
  
````
