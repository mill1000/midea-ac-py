"""Tests for the config flow."""

import logging
from unittest.mock import patch, AsyncMock, PropertyMock, MagicMock

import pytest
from homeassistant import config_entries
from homeassistant.const import (CONF_HOST, CONF_ID,
                                 CONF_PORT, CONF_TOKEN)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from msmart.lan import AuthenticationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.config_entries import ConfigEntryState
from custom_components.midea_ac.const import CONF_KEY, DOMAIN

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger(__name__)


async def test_config_flow_options(hass: HomeAssistant) -> None:
    """Test the config flow starts with a menu with manual and discover options."""
    # Check initial flow is a menu with two options
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["discover", "manual"]

    # Check discover flow can be started
    discover_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "discover"}
    )
    assert discover_form_result["type"] is FlowResultType.FORM
    assert discover_form_result["step_id"] == "discover"
    assert not discover_form_result["errors"]

    # Check manual flow can be started
    manual_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert manual_form_result["type"] is FlowResultType.FORM
    assert manual_form_result["step_id"] == "manual"
    assert not manual_form_result["errors"]


async def test_manual_flow(hass: HomeAssistant) -> None:
    """Test the manual flow validates input and failed connections return errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    invalid_input = [
        {
            CONF_HOST: None
        },
        {
            CONF_HOST: "localhost",
            CONF_PORT: None
        },
        {
            CONF_HOST: "localhost",
            CONF_PORT: 6444,
            CONF_ID: None
        }
    ]
    for input in invalid_input:
        with pytest.raises(InvalidData):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=input
            )

    with (patch("custom_components.midea_ac.config_flow.AC.refresh",
                return_value=False) as refresh_mock,
          patch("custom_components.midea_ac.config_flow.AC.authenticate",
                side_effect=AuthenticationError) as authenticate_mock):
        # Check manually configuring a V2 device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234"
            }
        )
        assert result
        # Refresh should be called
        refresh_mock.assert_awaited_once()
        # Authenticate shouldn't be called
        authenticate_mock.assert_not_awaited()
        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}

        refresh_mock.reset_mock()
        authenticate_mock.reset_mock()

        # Check manually configuring a V3 device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_TOKEN: "1234",
                CONF_KEY: "1234"

            }
        )
        assert result
        # Authenticate should be called
        authenticate_mock.assert_awaited_once()
        # Refresh should be not called
        refresh_mock.assert_not_awaited()
        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


# async def test_options_flow_init(hass: HomeAssistant) -> None:
#     """Test the integration options flow works and default options are set."""

#     config_entry = MockConfigEntry(
#             domain=DOMAIN,
#             data={
#                 CONF_HOST: "localhost",
#                 CONF_PORT: 6444,
#                 CONF_ID: "1234",
#                 CONF_TOKEN: None,
#                 CONF_KEY: None
#             },
#         )
    
#     test = AsyncMock()
#     test.id.return_value = "test"
#     test.get_capabilities = AsyncMock()
#     with patch("custom_components.midea_ac.AC", new=test):
#         # instance = MockDeviceClass.return_value
#         # _LOGGER.error(MockDeviceClass)
#         # MockDeviceClass.id = "1234"
#         # _LOGGER.error(MockDeviceClass.id)
#         # Mock the property with PropertyMock
#         # type(instance).id = PropertyMock(return_value="1234")

#         config_entry.add_to_hass(hass)
#         await hass.config_entries.async_setup(config_entry.entry_id)
#         await hass.async_block_till_done()

#     assert config_entry.entry_id in hass.data[DOMAIN]
#     assert config_entry.state is ConfigEntryState.LOADED

#     # # show initial form
#     # result = await hass.config_entries.options.async_init(config_entry.entry_id)
#     # assert "form" == result["type"]
#     # assert "init" == result["step_id"]
#     # assert {} == result["errors"]
#     # # Verify multi-select options populated with configured repos.
#     # assert {"sensor.ha_core": "HA Core"} == result["data_schema"].schema[
#     #     "repos"
#     # ].options
