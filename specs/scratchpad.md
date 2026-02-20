# Computation flow notes from author

## A. Simulation Setup

1. User defines a simulation setup using a settings.yaml file
2. User initiates a simulation in a script or notebook
3. The settings.yaml file is read in:
  1. A simulation_settings dataclass to store all intialization parameters and design configurations is created with default values (where feasible)
  2. User set parameters from the settings.yaml are checked for correctness against ranges / categorical options and overwrite the default values in the dataclass. Raise errors.
  3. Collective policies are copied over to each farm (per policy area)
  4. Check for any null parameters that can't be assigned with defaults. Raise errors.
  5. All data files needed to run a simulation are checked and confirmed. Raise errors.
  6. Other final checks are made. Raise errors.
4. A fully checked, ready to run simulation_settings dataclass has been generated / returned which includes all parameters and data required to run a simulation.

## B. Simulation Flow

### Phase 1. Initialize Simulation

1. Load the simulation_settings dataclass (now fully checked) and data files
2. Calculate infrastructure capacities from infrastructure design specifications
3. Calculate financing costs and
4. Initialize economic states: savings, etc.
5. Initialize water system state: water storage at 50%, aquifer depth, etc.
6. Initialize energy system state: grid connection, battery SOC at 50%, etc.

### Phase 2. Run Daily Loop with Monthly and Yearly Updating

### Phase 3. Run Balance Checks

1. After the simulation loop has completed, conservation checks are performed across (at least) the following areas to ensure conservation (input to output), no double counting, and correct loss functions (e.g. spoilage, roundtrip battery losses) were applied:
  - Crop yields to food processing outputs to market sales
  - Water balances
  - Energy balances, battery losses
  - Cash flows
2. Conservation report is generated with flags for any values that are suspicious or clearly out of range
3. Any data 

## C. Post Simulation Processing