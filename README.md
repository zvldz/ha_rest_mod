# Modified [rest](https://www.home-assistant.io/integrations/rest/) component for Home Assistant

## Installation
*__Manual mode__*

Place the `rest_mod` folder into your `custom_components` folder.

*__Adding custom repository to [HACS](https://hacs.xyz/)__*

Go to the Integrations page in HACS and select the three dots in the top right corner. Select Custom repositories.
Add repository url. Category - Integration. Read more on https://hacs.xyz/docs/faq/custom_repositories.

## Changes compared to the original component

* Sensor is always created, even if it could not get the data.
* Added `payload_template`(sensor/binary_sensor).
* Added `state_resource_template`(switch).
* Added `resource_template`(switch).
* Added configuration variable `proxy_url`(sensor/binary_sensor). Support for  socks/http proxies.
* `headers` with template support(sensor/binary_sensor/switch).


## Example
```yaml
# Example configuration.yaml entry
sensor:
  - platform: rest_mod
    resource: http://IP_ADDRESS/ENDPOINT
    proxy_url: "socks5://127.0.0.1:9050"
```

