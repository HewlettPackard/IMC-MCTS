// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

/*
 * C++ Wrapper Template for the Python SST-style simulation framework
 *
 * This template provides the interface that C++ components need to implement
 * to be compatible with the Python discrete-event framework.
 *
 * Include this header in your C++ components and implement the required
 * functions.
 */

#ifndef PYTHON_SST_WRAPPER_H
#define PYTHON_SST_WRAPPER_H

#include <string>
#include <map>
#include <memory>

extern "C" {
    // Component lifecycle functions
    void* create_component(const char* component_type, void* params);
    void destroy_component(void* component);
    void setup_component(void* component);
    void finish_component(void* component);
    
    // Simulation functions
    bool clock_tick(void* component, long long cycle);
    void handle_event(void* component, void* event);
    
    // Utility functions
    const char* get_component_name(void* component);
    void* get_component_params(void* component);
}

// Base class for Python SST compatible components
class PythonSSTComponent {
public:
    PythonSSTComponent(const std::string& type, void* params);
    virtual ~PythonSSTComponent() = default;
    
    // Pure virtual functions that must be implemented
    virtual void setup() = 0;
    virtual void finish() = 0;
    virtual bool clockTick(long long cycle) = 0;
    virtual void handleEvent(void* event) = 0;
    
    // Utility functions
    const std::string& getType() const { return component_type_; }
    const std::map<std::string, std::string>& getParams() const { return params_; }
    
protected:
    std::string component_type_;
    std::map<std::string, std::string> params_;
    bool initialized_;
    bool finalized_;
};

// Template for creating component-specific wrappers
template<typename ComponentClass>
class ComponentWrapper : public PythonSSTComponent {
public:
    ComponentWrapper(const std::string& type, void* params) 
        : PythonSSTComponent(type, params), component_(nullptr) {}
    
    ~ComponentWrapper() {
        if (component_) {
            delete component_;
        }
    }
    
    void setup() override {
        if (!component_) {
            // Create the actual component instance
            component_ = new ComponentClass();
            
            // Initialize with parameters
            // This would need to be customized based on your component's constructor
            // component_->initialize(params_);
        }
        
        if (component_) {
            component_->setup();
        }
        initialized_ = true;
    }
    
    void finish() override {
        if (component_) {
            component_->finish();
        }
        finalized_ = true;
    }
    
    bool clockTick(long long cycle) override {
        if (component_) {
            return component_->clockTick(cycle);
        }
        return true;
    }
    
    void handleEvent(void* event) override {
        if (component_) {
            // Convert event to appropriate type
            // This would need to be customized based on your event system
            component_->handleEvent(event);
        }
    }
    
private:
    ComponentClass* component_;
};

// Global component registry
class ComponentRegistry {
public:
    static ComponentRegistry& getInstance() {
        static ComponentRegistry instance;
        return instance;
    }
    
    void registerComponent(const std::string& type, 
                          std::function<PythonSSTComponent*(const std::string&, void*)> creator) {
        creators_[type] = creator;
    }
    
    PythonSSTComponent* createComponent(const std::string& type, void* params) {
        auto it = creators_.find(type);
        if (it != creators_.end()) {
            return it->second(type, params);
        }
        return nullptr;
    }
    
private:
    std::map<std::string, std::function<PythonSSTComponent*(const std::string&, void*)>> creators_;
};

// Macro to register a component type
#define REGISTER_PYTHON_SST_COMPONENT(ComponentType, ComponentClass) \
    static bool ComponentType##_registered = []() { \
        ComponentRegistry::getInstance().registerComponent( \
            #ComponentType, \
            [](const std::string& type, void* params) -> PythonSSTComponent* { \
                return new ComponentWrapper<ComponentClass>(type, params); \
            } \
        ); \
        return true; \
    }();

#endif // PYTHON_SST_WRAPPER_H
