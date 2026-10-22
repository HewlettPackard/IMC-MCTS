// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * C++ Wrapper Implementation Template for Python SST Integration
 * 
 * This file provides the implementation of the C interface functions
 * that allow Python to interact with C++ components.
 */

#include "cpp_wrapper_template.h"
#include <iostream>
#include <cstring>

// Global component registry
static std::map<void*, std::unique_ptr<PythonSSTComponent>> components;

// C interface functions
extern "C" {

void* create_component(const char* component_type, void* params) {
    if (!component_type) {
        std::cerr << "Error: component_type is null" << std::endl;
        return nullptr;
    }
    
    std::string type(component_type);
    auto component = ComponentRegistry::getInstance().createComponent(type, params);
    
    if (component) {
        void* handle = static_cast<void*>(component);
        components[handle] = std::unique_ptr<PythonSSTComponent>(component);
        return handle;
    }
    
    std::cerr << "Error: Failed to create component of type " << type << std::endl;
    return nullptr;
}

void destroy_component(void* component) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            components.erase(it);
        }
    }
}

void setup_component(void* component) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            it->second->setup();
        }
    }
}

void finish_component(void* component) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            it->second->finish();
        }
    }
}

bool clock_tick(void* component, long long cycle) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            return it->second->clockTick(cycle);
        }
    }
    return true;
}

void handle_event(void* component, void* event) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            it->second->handleEvent(event);
        }
    }
}

const char* get_component_name(void* component) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            return it->second->getType().c_str();
        }
    }
    return nullptr;
}

void* get_component_params(void* component) {
    if (component) {
        auto it = components.find(component);
        if (it != components.end()) {
            return static_cast<void*>(const_cast<std::map<std::string, std::string>*>(&it->second->getParams()));
        }
    }
    return nullptr;
}

} // extern "C"

// PythonSSTComponent implementation
PythonSSTComponent::PythonSSTComponent(const std::string& type, void* params)
    : component_type_(type), initialized_(false), finalized_(false) {
    
    // Convert params from Python dict to C++ map
    if (params) {
        // This is a simplified conversion - in practice, you'd need to properly
        // marshal the Python dictionary to C++ map
        // For now, we'll just store the pointer
        params_["raw_params"] = std::to_string(reinterpret_cast<uintptr_t>(params));
    }
}

// Example component registration
// Add entries here for your specific components:

/*
// Example: Register an Accelerator 5x5 System component
#include "accelerator_5x5_system.h"

REGISTER_PYTHON_SST_COMPONENT(Accelerator5x5System, Accelerator5x5System);

// Example: Register a Selection Unit component  
#include "selection_unit.h"

REGISTER_PYTHON_SST_COMPONENT(SelectionUnit, SelectionUnit);

// Example: Register an Expansion Unit component
#include "expansion_unit.h"

REGISTER_PYTHON_SST_COMPONENT(ExpansionUnit, ExpansionUnit);

// Example: Register a Rollout Unit component
#include "rollout_unit.h"

REGISTER_PYTHON_SST_COMPONENT(RolloutUnit, RolloutUnit);

// Example: Register a Backpropagation Unit component
#include "backpropagation_unit.h"

REGISTER_PYTHON_SST_COMPONENT(BackpropagationUnit, BackpropagationUnit);

// Example: Register an FSM Controller component
#include "fsm_controller.h"

REGISTER_PYTHON_SST_COMPONENT(FSMController, FSMController);
*/
