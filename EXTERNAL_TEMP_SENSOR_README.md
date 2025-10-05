# External Temperature Sensor Support for Midea AC Integration

This modification adds support for using an external temperature sensor instead of the AC unit's internal temperature sensor for thermostat control in Home Assistant.

## Features Added

- **External Temperature Sensor Override**: Configure any Home Assistant temperature sensor entity to be used instead of the AC's internal sensor
- **Fallback Protection**: Automatically falls back to the internal sensor if the external sensor is unavailable or reports invalid data
- **Configuration UI**: Easy setup through the Home Assistant configuration options interface
- **State Attributes**: View both internal and external temperature readings in the entity attributes
- **Logging**: Debug and warning messages to help troubleshoot sensor issues

## How to Use

### 1. Installation
Copy the modified integration files to your Home Assistant custom_components directory:
```
custom_components/midea_ac/
├── __init__.py
├── climate.py          # Modified - includes external sensor support
├── config_flow.py      # Modified - includes new configuration option
├── const.py           # Modified - includes new constant
├── coordinator.py
├── translations/
│   └── en.json        # Modified - includes new translation strings
└── ... (other files)
```

### 2. Setup External Temperature Sensor
1. Go to **Settings** → **Devices & Services**
2. Find your Midea AC integration
3. Click **Configure** (or the three dots → **Configure**)
4. In the **External Temperature Sensor** field, enter the entity ID of your temperature sensor
   - Example: `sensor.living_room_temperature`
   - Example: `sensor.xiaomi_temperature_humidity_sensor_temperature`
5. Click **Submit**

### 3. Restart Home Assistant
After configuration, restart Home Assistant to apply the changes.

## How It Works

### Temperature Reading Logic
1. **External Sensor Configured**: The integration checks if an external temperature sensor is configured
2. **External Sensor Available**: If configured, it reads the temperature from the external sensor
3. **Fallback**: If the external sensor is unavailable, has an invalid state, or returns an error, it automatically falls back to the AC's internal sensor
4. **Logging**: All sensor reads and fallbacks are logged for debugging

### State Attributes
The climate entity will show additional attributes when an external sensor is configured:
- `internal_temperature`: The AC's internal temperature reading (always available)
- `external_temp_sensor`: The entity ID of the configured external sensor
- `external_temp_sensor_state`: The current state of the external sensor

### Example Climate Entity Attributes
```yaml
# Without external sensor
follow_me: False
error_code: 0
internal_temperature: 22.5

# With external sensor configured
follow_me: False
error_code: 0
internal_temperature: 22.5
external_temp_sensor: sensor.living_room_temperature
external_temp_sensor_state: 24.2
```

## Supported External Sensors

Any Home Assistant sensor entity that reports temperature as a numeric value can be used:
- Zigbee temperature sensors (Xiaomi, Aqara, etc.)
- Z-Wave temperature sensors
- ESPHome temperature sensors
- Generic MQTT temperature sensors
- Weather station sensors
- Other climate entity temperatures

## Configuration Examples

### Basic Configuration
```
External Temperature Sensor: sensor.living_room_temperature
```

### Advanced Examples
```
# Xiaomi sensor
sensor.lumi_weather_temperature

# ESPHome sensor
sensor.bedroom_temperature

# Weather integration
weather.home.temperature

# Another thermostat's temperature
climate.other_thermostat.current_temperature
```

## Troubleshooting

### Check the Logs
1. Go to **Settings** → **System** → **Logs**
2. Look for messages from `custom_components.midea_ac.climate`
3. Debug messages will show which sensor is being used
4. Warning messages will indicate fallback scenarios

### Common Issues

**External sensor not working:**
- Verify the entity ID is correct
- Check that the sensor is available and reporting numeric values
- Look for warning messages in the logs

**Temperature not updating:**
- The external sensor must report temperature updates for the climate entity to update
- Check that the external sensor is working and updating regularly

**Fallback to internal sensor:**
- This is normal behavior when the external sensor is unavailable
- Check the sensor's availability in Developer Tools → States

### Debug Information
Enable debug logging for detailed information:
```yaml
# configuration.yaml
logger:
  logs:
    custom_components.midea_ac.climate: debug
```

## Benefits

### Improved Accuracy
- Use a more accurate or better-positioned temperature sensor
- Place sensors away from direct AC airflow for better readings
- Use sensors with higher precision or faster response times

### Better Control
- More responsive temperature control
- Better representation of actual room temperature
- Avoid temperature fluctuations from AC's internal sensor placement

### Flexibility
- Use existing sensors from your smart home setup
- No need for additional hardware
- Easy to switch between different sensors

## Technical Details

### Files Modified
1. **const.py**: Added `CONF_EXTERNAL_TEMP_SENSOR` constant
2. **config_flow.py**: Added external sensor option to configuration flow
3. **climate.py**: Modified `current_temperature` property to use external sensor
4. **translations/en.json**: Added UI text for the new option

### Implementation Notes
- The external sensor reading is cached per property access
- Fallback logic ensures the thermostat always has a temperature reading
- All sensor access errors are caught and logged
- The internal temperature is always available in state attributes for comparison

## Example Use Cases

1. **Better Room Coverage**: Place a sensor in the center of the room instead of relying on the AC's wall-mounted position
2. **Multi-Zone Control**: Use a sensor that averages multiple room temperatures
3. **Avoid Direct Airflow**: Use a sensor positioned away from the AC's direct air output
4. **Higher Precision**: Use a more accurate temperature sensor than the AC's built-in sensor
5. **Smart Home Integration**: Leverage existing temperature sensors from your broader smart home setup

## Future Enhancements

Potential future improvements could include:
- Support for multiple external sensors with averaging
- Temperature offset configuration for calibration
- Humidity sensor override support
- Sensor selection automation based on room occupancy

---

**Note**: This modification maintains full backward compatibility. Existing installations will continue to work unchanged if no external sensor is configured.
