// SPDX-License-Identifier: MIT
// Standalone adapter to the separately licensed, pinned NeuroSim SAR model.
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <vector>
#include "Param.h"
#include "SarADC.h"

Param *param = nullptr;

int main(int argc, char **argv) {
    if (argc != 9) return 2;
    Param settings;
    param = &settings;
    settings.technode = std::stoi(argv[1]);
    settings.deviceroadmap = std::stoi(argv[2]);
    int bits = std::stoi(argv[3]);
    int lanes = std::stoi(argv[4]);
    double resistance = std::stod(argv[5]);
    double clock = std::stod(argv[6]);
    settings.readVoltage = std::stod(argv[7]);
    settings.temp = std::stoi(argv[8]);
    InputParameter input{};
    input.processNode = settings.technode;
    input.deviceRoadmap = settings.deviceroadmap == 1 ? HP : LSTP;
    input.temperature = settings.temp;
    input.transistorType = conventional;
    Technology technology;
    technology.Initialize(input.processNode, input.deviceRoadmap, input.transistorType);
    MemCell cell{};
    SarADC adc(input, technology, cell);
    adc.Initialize(lanes, 1 << bits, clock, 16);
    adc.CalculateUnitArea();
    adc.CalculateArea(0, 100e-6, NONE);
    adc.CalculateLatency(1);
    adc.CalculatePower(std::vector<double>(lanes, resistance), 1);
    std::cout << "node_nm,roadmap,bits,lanes,column_ohm,clock_hz,read_v,temp_k,vdd_v,area_um2,latency_ns,energy_pj,reported_leakage_w\n";
    std::cout << std::setprecision(17) << settings.technode << ',' << settings.deviceroadmap
              << ',' << bits << ',' << lanes << ',' << resistance << ',' << clock << ','
              << settings.readVoltage << ',' << settings.temp << ',' << technology.vdd << ','
              << adc.area * 1e12 << ',' << adc.readLatency * 1e9 << ','
              << adc.readDynamicEnergy * 1e12 << ',' << adc.leakage << '\n';
}
