# Daikin One for Home Assistant

![GitHub release (latest by date)](https://img.shields.io/github/v/release/zlangbert/ha-daikinone?style=flat-square) [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A custom component for Home Assistant to integrate with Daikin One+ smart HVAC systems. This integration allows you to control your thermostats and view all the telemetry reported by your equipment.

<!-- TOC -->
* [Daikin One for Home Assistant](#daikin-one-for-home-assistant)
  * [Features](#features)
  * [Todo](#todo)
  * [Supported Equipment](#supported-equipment)
    * [Thermostats](#thermostats)
    * [Air Handlers](#air-handlers)
    * [Heat Pumps](#heat-pumps)
    * [Furnaces](#furnaces)
  * [Installation](#installation)
    * [Install via HACS](#install-via-hacs)
    * [Manual Install](#manual-install)
<!-- TOC -->

## Features

* Controllable climate entities for each thermostat
* All HVAC modes supported by the Daikin One+ system, including Emergency Heat
* Intelligent handling of thermostat updates for ultra-fast response times
* Sensors for status, temperatures, airflow, demand, etc. for all connected equipment

<img src="docs/dashboard.png" width="350" alt="dashboard example">

Dashboard source can be found [here](docs/dashboard.yaml) if you'd like you use it as a starting point for your own dashboard.

## Todo

* Weather entities for each thermostat
* Outdoor air quality
* Support for additional equipment types

## Supported Equipment

The following is the list of currently confirmed working equipment.

If you have a Daikin One+ system and your equipment is not listed here, please open an issue and we can work on adding support. Your raw Daikin API data can be retrieved by clicking "Download Diagnostics" on a thermostat's device page in Home Assistant. That information will be required to add support for your equipment.

### Thermostats

* One Touch Smart Thermostat

### Air Handlers

* [MBVC Modular Blower](https://daikincomfort.com/products/heating-cooling/whole-house/air-handlers-coils/mbvc-modular)

### Heat Pumps

* [DZ9VC](https://daikincomfort.com/products/heating-cooling/whole-house/heat-pump/dz9vc)
* [DZ6VS](https://daikincomfort.com/products/heating-cooling/whole-house/heat-pump/daikin-fit-heat-pump-dz6vs)

### Air Conditioners

* [DX6VS](https://daikincomfort.com/products/heating-cooling/whole-house/air-conditioner/daikin-fit-dx6vs)

### Furnaces

* [DM97MC](https://daikincomfort.com/products/heating-cooling/whole-house/gas-furnaces/dm97mc)
* [DM80VC](https://daikincomfort.com/products/heating-cooling/whole-house/gas-furnaces/dm80vc)

## Installation

### Install via HACS

_HACS must be [installed](https://hacs.xyz/docs/installation/prerequisites) before following these steps._

1. Log into your Home Assistant instance and open HACS via the sidebar on the left.
2. In the HACS console, open **Integrations**.
3. On the integrations page, select the "vertical dots" icon in the top-right corner, and select **Custom repositories**.
4. Paste `https://github.com/zlangbert/ha-daikinone` into the **Add custom repository URL** box and select **Integration** in the **Category** menu.
5. Select **Add**.
6. Restart Home Assistant
7. Click the below button to add the integration and start setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=daikinone)

### Manual Install

_A manual installation is more risky than installation via HACS. You must be familiar with how to SSH into Home Assistant and working in the Linux shell to perform these steps._

1. Download or clone this repository
2. Copy the `custom_components/daikinone` folder from the repository to your Home Assistant `custom_components` folder
3. Restart Home Assistant
4. Click the below button to add the integration and start setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=daikinone)
