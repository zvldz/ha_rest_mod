"""Support for RESTful API sensors."""
import json
import logging
from xml.parsers.expat import ExpatError

from jsonpath import jsonpath
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
import homeassistant.helpers.config_validation as cv

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import CONF_JSON_ATTRS, CONF_JSON_ATTRS_PATH, CONF_PAYLOAD_TEMPLATE
from .entity import RestEntity
from .schema import RESOURCE_SCHEMA, SENSOR_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **SENSOR_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the RESTful sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, SENSOR_DOMAIN, discovery_info
        )
    else:
        conf = config
        coordinator = None
        rest = create_rest_data_from_config(hass, conf)
        await rest.async_update(log_errors=False)

    name = conf.get(CONF_NAME)
    unit = conf.get(CONF_UNIT_OF_MEASUREMENT)
    device_class = conf.get(CONF_DEVICE_CLASS)
    state_class = conf.get(CONF_STATE_CLASS)
    json_attrs = conf.get(CONF_JSON_ATTRS)
    json_attrs_path = conf.get(CONF_JSON_ATTRS_PATH)
    value_template = conf.get(CONF_VALUE_TEMPLATE)
    force_update = conf.get(CONF_FORCE_UPDATE)
    resource_template = conf.get(CONF_RESOURCE_TEMPLATE)
    payload_template = config.get(CONF_PAYLOAD_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    async_add_entities(
        [
            RestSensorMod(
                coordinator,
                rest,
                name,
                unit,
                device_class,
                state_class,
                value_template,
                json_attrs,
                force_update,
                resource_template,
                json_attrs_path,
                payload_template,
            )
        ],
    )


class RestSensorMod(RestEntity, SensorEntity):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        coordinator,
        rest,
        name,
        unit_of_measurement,
        device_class,
        state_class,
        value_template,
        json_attrs,
        force_update,
        resource_template,
        json_attrs_path,
        payload_template,
    ):
        """Initialize the REST sensor."""
        super().__init__(
            coordinator, rest, name, resource_template, force_update, payload_template
        )
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self._json_attrs = json_attrs
        self._attributes = None
        self._json_attrs_path = json_attrs_path

        self._attr_native_unit_of_measurement = self._unit_of_measurement
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _update_from_rest_data(self):
        """Update state from the rest data."""
        value = self.rest.data
        _LOGGER.debug("[%s] Data fetched from resource: %s", self._name, value)
        if self.rest.headers is not None:
            # If the http request failed, headers will be None
            content_type = self.rest.headers.get("content-type")

            if content_type and (
                content_type.startswith("text/xml")
                or content_type.startswith("application/xml")
                or content_type.startswith("application/xhtml+xml")
            ):
                try:
                    value = json.dumps(xmltodict.parse(value))
                    _LOGGER.debug("[%s] JSON converted from XML: %s", self._name, value)
                except ExpatError:
                    _LOGGER.warning(
                        "[%s] REST xml result could not be parsed and converted to JSON",
                        self._name
                    )
                    _LOGGER.debug("[%s] Erroneous XML: %s", self._name, value)

        if self._json_attrs:
            self._attributes = {}
            if value:
                try:
                    json_dict = json.loads(value)
                    if self._json_attrs_path is not None:
                        json_dict = jsonpath(json_dict, self._json_attrs_path)
                    # jsonpath will always store the result in json_dict[0]
                    # so the next line happens to work exactly as needed to
                    # find the result
                    if isinstance(json_dict, list):
                        json_dict = json_dict[0]
                    if isinstance(json_dict, dict):
                        attrs = {
                            k: json_dict[k] for k in self._json_attrs if k in json_dict
                        }
                        self._attributes = attrs
                    else:
                        _LOGGER.warning(
                            "[%s] JSON result was not a dictionary"
                            " or list with 0th element a dictionary",
                            self._name
                        )
                except ValueError:
                    _LOGGER.warning("[%s] REST result could not be parsed as JSON", self._name)
                    _LOGGER.debug("[%s] Erroneous JSON: %s", self._name, value)

            else:
                _LOGGER.warning("[%s] Empty reply found when expecting JSON data", self._name)

        if value is not None and self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, None
            )

        if value is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._state = value
            return

        self._state = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )
