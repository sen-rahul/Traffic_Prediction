# Traffic_Prediction

## Table of Contents
1. [Project Overview](#project-overview)
2. [Project Structure](#project-structure)
3. [Data Sources](#data-sources)
4. [Installation and Setup](#installation-and-setup)
5. [Key Components](#key-components)
   - [Data Downloader](#data-downloader)
   - [Notebooks](#notebooks)
6. [Data Preparation](#data-preparation)
7. [Model Architecture](#model-architecture)
8. [Decision Support System (DSS)](#decision-support-system-dss)
9. [Usage](#usage)
10. [Evaluation](#evaluation)
## Project Overview
This project introduces a novel architecture called DualGAT-Trans, which extracts spatial and temporal features from traffic data. It incorporates a Transformer component specifically designed to focus on relevant timeframes. Additionally, it implements a Decision Support System (DSS) for intelligent lane reversals. DualGAT-Trans is compared against architectures based on Graph Convolutional Networks (GCN) and Convolutional Neural Networks (CNN) to evaluate its effectiveness in traffic prediction tasks. The system utilizes real-world traffic data, weather information, and incident reports to provide accurate traffic predictions and optimize traffic flow through adaptive lane management.
## Project Structure
```
.
├── data_downloader
│   ├── config.ini
│   ├── data_downloader.py
│   └── db_operations.py
├── notebooks
│   ├── config.py
│   ├── data_loader.ipynb
│   ├── eda.ipynb
│   ├── main.ipynb
│   └── model.ipynb
└── requirements.txt
```
## Data Sources
1. **Performance Measurement System (PeMS)**: Managed by the California Department of Transportation (CalTrans), PeMS provides real-time traffic information from over 39,000 sensors across California's freeway network.
   - Traffic Data: 5-minute interval data on vehicle counts, average speed, and lane occupancy.
   - Station Metadata: Information about station detectors, including location and other relevant details.
   - Incident Reports: Comprehensive data on time, location, duration, and severity of freeway incidents.
2. **Weather Data**: Sourced from the Visual Crossing website, providing hourly weather information including precipitation, visibility, and snow conditions.
## Installation and Setup
1. Clone the repository:
   ```
   git clone https://github.com/sen-rahul/Traffic_Prediction.git
   ```
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
3. Configure the `config.ini` file in the `data_downloader` directory with your credentials and paths to download the dataset and create database.
## Key Components
### Data Downloader
- **data_downloader.py**: 
  - Contains the `PEMSConnector` class for automated data collection from the PeMS website.
  - Implements web scraping with login credentials to download traffic data.
  - Configurable via config.ini for credentials, paths, and download parameters.
  - Performs file downloads, table creation, and data insertion.
  - Downloads weather data from the VisualCrossing API and stores it in a separate table.
- **db_operations.py**: 
  - Manages database operations using SQLite3.
  - Creates relevant tables and inserts downloaded data.
  - Implements indexing on the timestamp column for optimized data retrieval.
- **config.ini**: 
  - Stores configuration details including user credentials, file paths, and date ranges for data collection.
### Notebooks
- **config.py**: 
  - Contains configuration settings for the traffic prediction model and data processing.
  - Defines parameters such as features, target variables, train-test split ratio, and model design and hyperparameters.
- **data_loader.ipynb**: 
  - Handles comprehensive data preparation, including:
    - Fetching and quality checks for station metadata and traffic data.
    - Data reduction, tranformation and linkage.
    - Extracts basic temporal features.
    - Integration of weather and incident data with traffic data.
- **eda.ipynb**: 
  - Conducts Exploratory Data Analysis, including:
    - Analysis of key variables, temporal columns, number of lanes and lag features.
    - Weather impact analysis and incident-related hypothesis testing.
    - Spatial dependency analysis using hierarchical clustering.
- **model.ipynb**: 
  - Implements the traffic prediction models:
    - Creates graph and grid structures for spatial-temporal data representation.
    - Defines model architectures for CNN, GCN, and GAT.
    - Implements the Decision Support System using reinforcement learning.
- **main.ipynb**: 
  - Serves as the main execution notebook for the entire pipeline:
    - Data sorting, splitting, and standardisation.
    - Creation of input structures for different model types.
    - Model training and evaluation for both short-term and long-term predictions.
    - Visualization of results and model performance analysis.
    - DSS application using Q-Learning.
## Data Preparation
1. **Data Reduction**: 
   - Focuses on District 12 due to its extensive sensor network.
   - Selects traffic data for timeframe as January 2023, sensor types `HV` and `ML`
   - Implements dynamic region selection, concentrating on the Tustin area with 41 sensors.
2. **Data Transformation**: 
   - Aligns different data granularities (5-minute traffic data with hourly weather data).
3. **Data Linkage**: 
   - Merges station_5min traffic data with metadata using freeway_id and station as keys.
   - Integrates transformed weather data based on timestamps.
   - Adds incident flags to traffic data, considering timestamp, duration, and location.
## Model Architecture
The project implements three advanced model architectures designed to capture complex spatial-temporal dynamics in traffic data. Each architecture consists of three main stages: Spatial Feature Extraction, Temporal Dependency Capture, and Prediction Generation. The models process two parallel inputs to leverage both recent and historical traffic patterns.
### Model Types
1. **DualCNN-Trans**
2. **DualGCN-Trans**
3. **DualGAT-Trans**
### Input Data Structure
Each model processes two parallel inputs:
1. **Recent Data**: 
   - Timeframe: 30 minutes before the latest available timestamp
   - Purpose: Capture current traffic trends
2. **Historical Data**: 
   - Timeframe: Same time 7 days earlier, with a 30-minute window before and after
   - Purpose: Incorporate weekly patterns and trends
### Data Organization
- Each timestep is represented by a graph or grid consisting of 41 nodes or rows, corresponding to the 41 stations.
- Eight features are used for modeling: lagged total flow and its corresponding time, day of the week, average speed, average occupancy, number of lanes, incident flag, and visibility.
### Stage 1: Spatial Feature Extraction
This stage differs for each model type:
1. **CNN Model**:
   - Input Structure: Grid where each row represents a reference station and its four nearest neighboring stations within a 1-mile radius.
   - Process:
     - Applies filters of size 1x8 with a stride of 1x8, combining similar features for each station set at each timestep.
     - Uses max pooling with a size of 1x5 to aggregate results across the five stations.
   - Output: Combined record for each timestep.
2. **GCN and GAT Models**:
   - Input Structure: Graph where each node represents a station, containing time-series data for its corresponding station.
   - Edge Definition: Nodes are interconnected by edges within a 1-mile driving distance.
   - Process:
     - GCN: Applies graph convolutions to aggregate information from neighboring nodes.
     - GAT: Uses attention mechanisms to weigh the importance of different neighboring nodes.
### Stage 2: Temporal Dependency Capture
All models use a Transformer for this stage:
- Input: Concatenated features from the spatial extraction stage (both recent and historical data).
- Process: 
  - Applies self-attention mechanisms to capture temporal dependencies.
  - Reweights the importance of different time steps based on their relevance to the prediction task.
- Configuration:
  - Number of heads: 8
  - Encoder layers: 1
  - Decoder layers: 1
### Stage 3: Prediction Generation
All models use a Fully Connected (FC) layer for the final prediction:
- Input: Output from the Transformer stage.
- Process: Maps the high-dimensional features to the desired output dimensions.
- Output: Continuous traffic predictions for each station.
### Model Parameters
- Batch Size: 24
- Hidden Channels: 8
- Learning Rate: 0.001
- Epochs: 10
- CNN-specific:
  - Filter Size: 1x8
  - Stride: 1x8
  - Pooling Layers: 2
  - Pooling Size: 1x5
  - Pooling Stride: 1x5
- GCN/GAT-specific:
  - Graph Layer Heads: 4
### Training Process
1. The dataset is sorted by time and station identifiers to maintain chronological order.
2. Data is split into training (80%) and testing (20%) sets.
3. StandardScaling is applied to achieve zero mean and unit variance.
4. The standardized data is input into the CNN, GCN, and GAT models for feature extraction.
5. The model is trained using the Adam optimizer.
### Prediction Scenarios
The models are trained and evaluated on two prediction scenarios:
1. **Short-term Prediction**: Next 30 minutes
2. **Long-term Prediction**: Upcoming 6th hour (30-minute window)
This dual-scenario approach allows the model to capture both immediate traffic fluctuations and longer-term patterns, providing a comprehensive traffic prediction system.
## Decision Support System (DSS)
The DSS implements an intelligent lane reversal system using reinforcement learning:
- Utilizes Q-learning to decide on lane reversals based on predicted traffic conditions.
- Compares predicted traffic data from the nearest opposite station to the reference station.
- Implements a reward system promoting beneficial lane reversals.
- Validates proposed actions against actual traffic counts for refined decision-making.
## Usage
1. Configure the `config.ini` file with appropriate credentials and paths.
2. Run the data downloader:
   ```
   python data_downloader/data_downloader.py
   ```
3. Execute the notebooks for the following:
   For EDA - `eda.ipynb`
   For Model Training & Results - `main.ipynb`
## Evaluation
The models are evaluated using:
- Mean Absolute Error (MAE)
- Root Mean Squared Error (RMSE)
Performance is assessed for both short-term (next 30 minutes) and long-term (6 hours ahead) predictions, with visualizations at overall and station-specific levels.

