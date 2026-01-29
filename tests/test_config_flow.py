"""Tests for the config flow."""

import logging
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_ID, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from msmart.device import AirConditioner as AC
from msmart.lan import AuthenticationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.midea_ac.const import (CONF_BEEP, CONF_DEVICE_TYPE,
                                              CONF_KEY, DOMAIN)

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


async def test_manual_flow_invalid_input(hass: HomeAssistant) -> None:
    """Test the manual flow validates input."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Test various invalid input combinations
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
        },
        {
            CONF_HOST: "localhost",
            CONF_PORT: 6444,
            CONF_ID: "1234",
            CONF_DEVICE_TYPE: None
        }
    ]
    for input in invalid_input:
        with pytest.raises(InvalidData):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=input
            )

    # Check that invalid token/keys formats throw an error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "localhost",
            CONF_PORT: 6444,
            CONF_ID: "1234",
            CONF_DEVICE_TYPE: "AC",
            CONF_TOKEN: "not_hex_string",
            CONF_KEY: "also_not_hex"

        }
    )
    assert result

    # Inputs should be marked as invalid
    assert result["errors"] == {
        CONF_TOKEN: "invalid_hex_format",
        CONF_KEY: "invalid_hex_format"
    }


async def test_manual_flow_cant_connect_v2(hass: HomeAssistant) -> None:
    """Test the manual flow returns error when connection fails on V2 devices."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch construct to build a mock device that isn't online
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        # Configure V2 device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "AC"
            }
        )
        assert result

        # Refresh should be called
        device.refresh.assert_awaited_once()

        # Authenticate should be called
        device.authenticate.assert_not_awaited()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_cant_connect_v3(hass: HomeAssistant) -> None:
    """Test the manual flow returns error when authenticate succeeds but refresh fails."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch construct to build a mock device that isn't online
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        # Configure V3 device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "AC",
                CONF_TOKEN: "1234",
                CONF_KEY: "1234",

            }
        )
        assert result

        # Authenticate should be called
        device.authenticate.assert_awaited_once()

        # Refresh should be not called
        device.refresh.assert_awaited_once()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_cant_authenticate(hass: HomeAssistant) -> None:
    """Test the manual flow returns error when authentication fails."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch construct to build a mock device that fails to authenticate
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.authenticate = AsyncMock(side_effect=AuthenticationError)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        # Configure V3 device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "AC",
                CONF_TOKEN: "1234",
                CONF_KEY: "1234",
            }
        )
        assert result

        # Authenticate should be called
        device.authenticate.assert_awaited_once()

        # Refresh should be not called
        device.refresh.assert_not_awaited()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_manual_flow_unsupported_device(hass: HomeAssistant) -> None:
    """Test the manual flow when an unsupported device is configured."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch construct to build a mock device that is online but unsupported
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=True)
        type(device).supported = PropertyMock(return_value=False)
        mock_construct.return_value = device

        # Configure the device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "AC"
            }
        )
        assert result

        # Refresh should be called
        device.refresh.assert_awaited_once()

        # Connection should fail
        assert result["errors"] == {"base": "unsupported_device"}


async def test_manual_flow_ac_device(hass: HomeAssistant) -> None:
    """Test the manual flow when creating an AC device."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch AC device refresh method
    with (patch("custom_components.midea_ac.config_flow.AC.refresh") as refresh_mock,
          patch("custom_components.midea_ac.config_flow.AC.online", new_callable=PropertyMock) as online_mock,
          patch("custom_components.midea_ac.config_flow.AC.supported", new_callable=PropertyMock) as supported_mock
          ):

        # Mock device online and supported
        online_mock.return_value = True
        supported_mock.return_value = True

        # Configure AC device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "AC",
            }
        )
        assert result

        # Refresh should be called
        refresh_mock.assert_awaited_once()

        # No errors
        assert "errors" not in result


async def test_manual_flow_cc_device(hass: HomeAssistant) -> None:
    """Test the manual flow when creating a CC device."""
    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert result

    # Patch CC device refresh method
    with (patch("custom_components.midea_ac.config_flow.CC.refresh") as refresh_mock,
          patch("custom_components.midea_ac.config_flow.CC.online", new_callable=PropertyMock) as online_mock,
          patch("custom_components.midea_ac.config_flow.CC.supported", new_callable=PropertyMock) as supported_mock
          ):

        # Mock device online and supported
        online_mock.return_value = True
        supported_mock.return_value = True

        # Configure CC device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_ID: "1234",
                CONF_DEVICE_TYPE: "CC",
            }
        )
        assert result

        # Refresh should be called
        refresh_mock.assert_awaited_once()

        # No errors
        assert "errors" not in result


async def test_options_flow_init(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration options flow works and default options are set."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Show options form
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["step_id"] == "init"
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch("custom_components.midea_ac.async_setup_entry",
               return_value=True) as mock_setup_entry:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_BEEP: False
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_BEEP: False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reconfigure_flow_invalid_input(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow validates input."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        }
    )
    assert result

    invalid_input = [
        {
            CONF_HOST: None
        },
        {
            CONF_HOST: "localhost",
            CONF_PORT: None
        }
    ]
    for input in invalid_input:
        with pytest.raises(InvalidData):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input=input
            )

    # Check that invalid token/keys formats throw an error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "localhost",
            CONF_PORT: 6444,
            CONF_TOKEN: "not_hex_string",
            CONF_KEY: "also_not_hex"

        }
    )
    assert result

    # Inputs should be marked as invalid
    assert result["errors"] == {
        CONF_TOKEN: "invalid_hex_format",
        CONF_KEY: "invalid_hex_format"
    }


async def test_reconfigure_flow_cant_connect_v2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow returns error when connection fails."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        }
    )
    assert result

    # Patch construct to build a mock device that isn't online
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.authenticate = AsyncMock()
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
            }
        )
        assert result

        # Refresh should be called
        device.refresh.assert_awaited_once()

        # Authenticate shouldn't be called
        device.authenticate.assert_not_awaited()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_cant_connect_v3(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow returns error when authenticate succeeds but refresh fails."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        }
    )
    assert result

    # Patch construct to build a mock device that isn't online
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.authenticate = AsyncMock()
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_TOKEN: "1234",
                CONF_KEY: "1234",
            }
        )
        assert result

        # Authenticate should be called
        device.authenticate.assert_awaited_once()

        # Refresh should be called
        device.refresh.assert_awaited_once()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_cant_authenticate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow returns error when authentication fails."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        }
    )
    assert result

    # Patch construct to build a mock device that can't authenticate
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.authenticate = AsyncMock(side_effect=AuthenticationError)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=False)
        mock_construct.return_value = device

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
                CONF_TOKEN: "1234",
                CONF_KEY: "1234"

            }
        )
        assert result

        # Authenticate should be called
        device.authenticate.assert_awaited_once()

        # Refresh should be not called
        device.refresh.assert_not_awaited()

        # Connection should fail
        assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unsupported_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow when an unsupported device is configured."""

    # Patch refresh and get_capabilities calls to allow integration to setup
    with (patch("custom_components.midea_ac.config_flow.AC.get_capabilities"),
          patch("custom_components.midea_ac.config_flow.AC.refresh")):
        # Add mock config entry to HASS and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        }
    )
    assert result

    # Patch construct to build a mock device that is online but unsupported
    with patch("custom_components.midea_ac.config_flow.Device.construct", autospec=True) as mock_construct:
        device = MagicMock(spec=AC)
        device.refresh = AsyncMock()
        type(device).online = PropertyMock(return_value=True)
        type(device).supported = PropertyMock(return_value=False)
        mock_construct.return_value = device

        # Manually configure a device
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "localhost",
                CONF_PORT: 6444,
            }
        )
        assert result

        # Refresh should be called
        device.refresh.assert_awaited_once()

        # Connection should fail
        assert result["errors"] == {"base": "unsupported_device"}
