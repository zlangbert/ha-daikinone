"""Catalog of Daikin API device-data fields.

Each constant binds an API key to its wire-encoding spec (from ``wire``),
so mapping code can decode a field with a single ``read(payload.data, F_*)``
call without repeating the sentinel/scale/unit details at every call site.
"""

from custom_components.daikinone.client.wire import (
    CelsiusField,
    FloatField,
    IntField,
    PercentField,
    RuntimeField,
    Sentinel,
    StringField,
    TempField,
)


# --- Thermostat field catalog ---

F_TEMP_INDOOR = CelsiusField("tempIndoor")
F_HUM_INDOOR = PercentField("humIndoor")
F_SETPOINT_HEAT = CelsiusField("hspActive")
F_SETPOINT_HEAT_MIN = CelsiusField("EquipProtocolMinHeatSetpoint")
F_SETPOINT_HEAT_MAX = CelsiusField("EquipProtocolMaxHeatSetpoint")
F_SETPOINT_COOL = CelsiusField("cspActive")
F_SETPOINT_COOL_MIN = CelsiusField("EquipProtocolMinCoolSetpoint")
F_SETPOINT_COOL_MAX = CelsiusField("EquipProtocolMaxCoolSetpoint")
F_TEMP_OUTDOOR = CelsiusField("tempOutdoor")
F_HUM_OUTDOOR = PercentField("humOutdoor")


# --- Air handler field catalog ---

# percent demands: uint8 encoded with 0.5 resolution
F_AH_FAN_REQ_DEMAND = IntField("ctAHFanRequestedDemand", Sentinel.U8, 0.5)
F_AH_FAN_CUR_DEMAND = IntField("ctAHFanCurrentDemandStatus", Sentinel.U8, 0.5)
F_AH_HEAT_REQ_DEMAND = IntField("ctAHHeatRequestedDemand", Sentinel.U8, 0.5)
F_AH_HEAT_CUR_DEMAND = IntField("ctAHHeatCurrentDemandStatus", Sentinel.U8, 0.5)
F_AH_HUM_REQ_DEMAND = IntField("ctAHHumidificationRequestedDemand", Sentinel.U8, 0.5)

F_AH_AIRFLOW = IntField("ctAHCurrentIndoorAirflow", Sentinel.U16)

F_AH_MODEL = StringField("ctAHModelNoCharacter1_15")
F_AH_SERIAL = StringField("ctAHSerialNoCharacter1_15")
F_AH_FIRMWARE = StringField("ctAHControlSoftwareVersion")
F_AH_MODE = StringField("ctAHMode")


# --- Furnace (IFC) field catalog ---

F_IFC_FAN_REQ_DEMAND = IntField("ctIFCFanRequestedDemandPercent", Sentinel.U8, 0.5)
F_IFC_FAN_CUR_DEMAND = IntField("ctIFCCurrentFanActualStatus", Sentinel.U8, 0.5)
F_IFC_HEAT_REQ_DEMAND = IntField("ctIFCHeatRequestedDemandPercent", Sentinel.U8, 0.5)
F_IFC_HEAT_CUR_DEMAND = IntField("ctIFCCurrentHeatActualStatus", Sentinel.U8, 0.5)
F_IFC_COOL_REQ_DEMAND = IntField("ctIFCCoolRequestedDemandPercent", Sentinel.U8, 0.5)
F_IFC_COOL_CUR_DEMAND = IntField("ctIFCCurrentCoolActualStatus", Sentinel.U8, 0.5)
F_IFC_HUM_REQ_DEMAND = IntField("ctIFCHumRequestedDemandPercent", Sentinel.U8, 0.5)
F_IFC_DEHUM_REQ_DEMAND = IntField("ctIFCDehumRequestedDemandPercent", Sentinel.U8, 0.5)

F_IFC_AIRFLOW = IntField("ctIFCIndoorBlowerAirflow", Sentinel.U16)

F_IFC_MODEL = StringField("ctIFCModelNoCharacter1_15")
F_IFC_SERIAL = StringField("ctIFCSerialNoCharacter1_15")
F_IFC_FIRMWARE = StringField("ctIFCControlSoftwareVersion")
F_IFC_MODE = StringField("ctIFCOperatingHeatCoolMode")


# --- Indoor (AH+IFC) shared ---

# uint16 encoded with 0.1 W resolution (deci-watt)
F_INDOOR_POWER = FloatField("ctIndoorPower", Sentinel.U16, 0.1)


# --- Outdoor unit field catalog ---

F_OD_MODEL = StringField("ctOutdoorModelNoCharacter1_15")
F_OD_SERIAL = StringField("ctOutdoorSerialNoCharacter1_15")
F_OD_FIRMWARE = StringField("ctOutdoorControlSoftwareVersion")
F_OD_INVERTER_FIRMWARE = StringField("ctOutdoorInverterSoftwareVersion")
F_OD_MODE = StringField("ctOutdoorMode")

F_OD_COMPRESSOR_RUNTIME = RuntimeField("ctOutdoorCompressorRunTime")

F_OD_COMPRESSOR_SPEED_TARGET = IntField("ctTargetCompressorspeed", Sentinel.U8)
F_OD_COMPRESSOR_SPEED_CURRENT = IntField("ctCurrentCompressorRPS", Sentinel.U16)
F_OD_FAN_TARGET_RPM = IntField("ctTargetODFanRPM", Sentinel.U8, 10)
F_OD_FAN_RPM = IntField("ctOutdoorFanRPM", Sentinel.U16)
F_OD_SUCTION_PRESSURE = IntField("ctOutdoorSuctionPressure", Sentinel.I16)
F_OD_EEV_OPENING = IntField("ctOutdoorEEVOpening", Sentinel.U8)

F_OD_HEAT_REQ_DEMAND = IntField("ctOutdoorHeatRequestedDemand", Sentinel.U8, 0.5)
F_OD_COOL_REQ_DEMAND = IntField("ctOutdoorCoolRequestedDemand", Sentinel.U8, 0.5)
F_OD_FAN_REQ_DEMAND = IntField("ctOutdoorFanRequestedDemandPercentage", Sentinel.U8, 0.5)
F_OD_FAN_REQ_AIRFLOW = IntField("ctOutdoorRequestedIndoorAirflow", Sentinel.U16)
F_OD_DEHUM_REQ_DEMAND = IntField("ctOutdoorDeHumidificationRequestedDemand", Sentinel.U8, 0.5)

# temperatures: int16, deci-degree Fahrenheit (default TempField settings)
F_OD_AIR_TEMP = TempField("ctOutdoorAirTemperature")
F_OD_COIL_TEMP = TempField("ctOutdoorCoilTemperature")
F_OD_DISCHARGE_TEMP = TempField("ctOutdoorDischargeTemperature")
F_OD_LIQUID_TEMP = TempField("ctOutdoorLiquidTemperature")
F_OD_DEFROST_TEMP = TempField("ctOutdoorDefrostSensorTemperature")
# inverter fin is the odd one out: uint8 raw-degree Celsius
F_OD_INVERTER_FIN_TEMP = TempField("ctInverterFinTemp", Sentinel.U8, scale=1, unit="C")

# outdoor power is uint16 encoded as deca-watt (x10)
F_OD_POWER = FloatField("ctOutdoorPower", Sentinel.U16, 10)
F_OD_COMPRESSOR_AMPS = FloatField("ctCompressorCurrent", Sentinel.U16, 0.1)
F_OD_INVERTER_AMPS = FloatField("ctInverterCurrent", Sentinel.U8, 0.1)
F_OD_FAN_MOTOR_AMPS = FloatField("ctODFanMotorCurrent", Sentinel.U8, 0.1)


# --- EEV coil field catalog ---

F_EEV_SERIAL = StringField("ctCoilSerialNoCharacter1_15")
F_EEV_FIRMWARE = StringField("ctCoilControlSoftwareVersion")
F_EEV_PRESSURE = IntField("ctEEVCoilPressureSensor", Sentinel.I16)
F_EEV_SUPERHEAT_TEMP = TempField("ctEEVCoilSuperHeatValue")
F_EEV_SUBCOOL_TEMP = TempField("ctEEVCoilSubCoolValue")
F_EEV_SUCTION_TEMP = TempField("ctEEVCoilSuctionTemperature")
