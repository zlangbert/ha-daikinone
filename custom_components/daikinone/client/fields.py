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
    UnitTypeField,
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

F_AH_UNIT_TYPE = UnitTypeField("ctAHUnitType")

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

F_IFC_UNIT_TYPE = UnitTypeField("ctIFCUnitType")

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

F_OD_UNIT_TYPE = UnitTypeField("ctOutdoorUnitType")

F_OD_MODEL = StringField("ctOutdoorModelNoCharacter1_15")
F_OD_SERIAL = StringField("ctOutdoorSerialNoCharacter1_15")
F_OD_FIRMWARE = StringField("ctOutdoorControlSoftwareVersion")
F_OD_INVERTER_FIRMWARE = StringField("ctOutdoorInverterSoftwareVersion")
F_OD_MODE = StringField("ctOutdoorMode")

F_OD_COMPRESSOR_RUNTIME = RuntimeField("ctOutdoorCompressorRunTime")

F_OD_HEAT_MAX_RPS = IntField("ctOutdoorHeatMaxRPS", Sentinel.U16)

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

F_COIL_UNIT_TYPE = UnitTypeField("ctCoilUnitType")

F_EEV_SERIAL = StringField("ctCoilSerialNoCharacter1_15")
F_EEV_FIRMWARE = StringField("ctCoilControlSoftwareVersion")
F_EEV_PRESSURE = IntField("ctEEVCoilPressureSensor", Sentinel.I16)
F_EEV_SUPERHEAT_TEMP = TempField("ctEEVCoilSuperHeatValue")
F_EEV_SUBCOOL_TEMP = TempField("ctEEVCoilSubCoolValue")
F_EEV_SUCTION_TEMP = TempField("ctEEVCoilSuctionTemperature")


# --- P1/P2 / S21 indoor-unit fields ---
#
# These fields are reported by Daikin mini- and multi-split systems.  Their
# zero values are retained: the raw API response must establish whether zero
# is a valid measurement for a particular model before it is filtered.
F_P1P2_UNIT_TYPE = UnitTypeField("P1P2UnitType")
F_P1P2_MODEL = StringField("P1P2IndoorUnitModelNameManual")
F_P1P2_SERIAL = StringField("P1P2IndoorUnitSerialNumber")
F_P1P2_MODE = IntField("mode", Sentinel.U8)
F_P1P2_INDOOR_TEMP = CelsiusField("tempIndoor")
F_P1P2_INDOOR_HUMIDITY = PercentField("humIndoor")
F_P1P2_HEAT_SETPOINT = CelsiusField("P1P2hspFromEquipment")
F_P1P2_COOL_SETPOINT = CelsiusField("P1P2cspFromEquipment")
F_P1P2_FAN_SPEED = IntField("P1P2IndoorUnitFanSpeed", Sentinel.U8)
F_P1P2_FLAP_SWING = IntField("P1P2IndoorUnitFlapSwing", Sentinel.U8)
F_P1P2_SUCTION_TEMP = CelsiusField("P1P2IndoorSuctionAirThermistor")
F_P1P2_DISCHARGE_TEMP = CelsiusField("P1P2IndoorUnitDischargeAirThermistor")
F_P1P2_OPERATING_TIME = IntField("P1P2IndoorUnitOperatingTime", Sentinel.U32)
F_P1P2_ENERGIZED_TIME = IntField("P1P2IndoorUnitEnergizedTime", Sentinel.U32)
F_P1P2_FAN_OPERATION_TIME = IntField("P1P2IndoorUnitFanOperationTime", Sentinel.U32)
F_P1P2_EEV_OPEN_PULSES = IntField("P1P2IndoorUnitEEVOpenPulses", Sentinel.U16)
F_P1P2_GAS_PIPE_TEMP = CelsiusField("P1P2IndoorUnitHeatExchangerGasPipeThermistor")
F_P1P2_HEAT_EXCHANGER_TEMP = CelsiusField("P1P2IndoorUnitHeatExchangerThermistor")
F_P1P2_FAN_TAP = IntField("P1P2IndoorUnitFanTap", Sentinel.U8)
F_P1P2_HUMIDIFIER = IntField("AuxHumidifierStatus", Sentinel.U8)
F_P1P2_DEHUMIDIFIER = IntField("AuxDehumidifierStatus", Sentinel.U8)
F_P1P2_DRAIN_PUMP = IntField("P1P2DrainPumpOnOff", Sentinel.U8)
F_P1P2_FLOAT_SWITCH = IntField("P1P2FloatOnOff", Sentinel.U8)
F_P1P2_ANTI_FREEZE = IntField("P1P2AntiFreezeControlOnOff", Sentinel.U8)
F_P1P2_ELECTRIC_HEATER = IntField("P1P2ElectricHeaterOnOff", Sentinel.U8)
F_P1P2_HUMIDIFIER_CONTROL = IntField("P1P2HumidifierOnOff", Sentinel.U8)
