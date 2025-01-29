"""Tests for the config flow."""

import pytest
from custom_components.midea_ac.const import DOMAIN
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.data_entry_flow import InvalidData
from homeassistant.const import (CONF_COUNTRY_CODE, CONF_HOST, CONF_ID,
                                 CONF_PORT, CONF_TOKEN)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and handle errors and successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    manual_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "manual"}
    )
    assert manual_form_result["type"] is FlowResultType.FORM
    assert manual_form_result["step_id"] == "manual"
    assert not manual_form_result["errors"]

    with pytest.raises(InvalidData):
        result = await hass.config_entries.flow.async_configure(
            manual_form_result["flow_id"],
            user_input={
                CONF_HOST: None
            }
        )
