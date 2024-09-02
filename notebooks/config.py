from datetime import datetime, timedelta

class Config():
    # Configuration for traffic prediction model settings

    # paths
    db_path = 'ADD_DATABASE_PATH' # add your database path
    osrm_path = 'http://router.project-osrm.org/route/v1/driving/'

    # Data Reduction Conditions
    # Station boundary region condition (filter-region): List of station IDs
    station_range = [1212741, 1203252, 1205139]
    # Traffic data conditions: Define start and end dates, and district filters
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 31)
    district_condition = [12]

    
    # Features and Target: List of input traffic features and target output
    features = ['time','dow','total_flow','avg_speed','avg_occupancy','lanes','incident_nearby','visibility']
    output = ['total_flow']

    # Train size: Fraction of data to be used for training
    train_size = 0.8 
    

    def create_y_range(pred_hour=0, y_ts_step=1):
        # Function to create the y-range for the model's output sequence

        # Data interval in minutes
        data_interval_mins = 5

        # Calculate the number of time steps per hour (12 steps per hour)
        hourly_steps = 60/data_interval_mins
        
        # Calculate half-hour steps for prediction range (6 steps per hour)
        half_hourly_steps = hourly_steps/2
        
        # Determine the start and end time steps for the prediction range
        y_ts_start = max(1,int(pred_hour * hourly_steps)) # Ensure at least one step
        y_ts_end = int(pred_hour * hourly_steps + half_hourly_steps) # 30-minute prediction window

        # Calculate the number of output channels based on the time step range
        output_channels = len(list(range(y_ts_start, y_ts_end + y_ts_step, y_ts_step)))

        # Return the start, end, step, and number of output channels
        return y_ts_start, y_ts_end, y_ts_step, output_channels

    def create_x_range(focus_timeframe, x_ts_step=1, length_start=-7, length_end=5):
        # Function to create the x-range for the model's input sequence
        
        # Determine the start and end time steps for the input sequence
        x_ts_start = -int(focus_timeframe) + length_start
        x_ts_end = -int(focus_timeframe) + length_end

        # Return the start, end, and step values for the input sequence
        return x_ts_start, x_ts_end, x_ts_step


        
    # model config
    batch_size = 24
    hidden_channels = 8
    learning_rate = 0.001
    epochs = 20
    
    cnn_filter_size = (1, 8)
    cnn_stride = (1, 8)
    cnn_padding = 0
    cnn_pooling_layers = 2
    cnn_pooling_size = (1, 5)
    cnn_pooling_stride = (1, 5)
    cnn_out_channels = 8
    
    grid_tf_head = 8
    graph_tf_nhead= 8

    # Model configuration parameters
    batch_size = 24
    hidden_channels = 8
    learning_rate = 0.001
    epochs = 10
    
    # CNN (Convolutional Neural Network) configuration parameters
    cnn_filter_size = (1, 8)
    cnn_stride = (1, 8)
    cnn_padding = 0
    cnn_pooling_layers = 2
    cnn_pooling_size = (1, 5)
    cnn_pooling_stride = (1, 5)
    cnn_out_channels = 8
    
    # Transformer model configuration 
    grid_tf_head = 8 # for Grid type 
    graph_tf_nhead = 8 # for Graph type
    

    
    def tf_fc_input_size(input_size, kernel_size, stride, padding, pooling_layers, pooling_size, pooling_stride):
        # Calculate the output size after applying CNN and pooling layers

        # Compute the size after the convolutional layer
        op_shape = (input_size - kernel_size + 2*padding)/stride + 1

        # Apply pooling layers iteratively
        for i in range(pooling_layers):
            op_shape = (op_shape - pooling_size)/pooling_stride + 1
        
        # Return the final output shape as an integer
        return int(op_shape)

        

    # Model design configuration
    def model_designs(num_stations, output_channels, model_type, **kwargs):
        # Generate model design based on the model type (Grid or Graph-based)

        # Number of attention heads for Graph Convolutional Networks (GCN) and Graph Attention Networks (GAT)
        graph_layer_heads = 4    
        
        if model_type == 'Grid':
            # Model configuration for Grid-based architecture
            return {
            'CNN': [
                dict(layer_no=1, model='CNN', in_channels=1, kernel_size=kwargs['cnn_filter_size'], stride=kwargs['cnn_stride'], out_channels=kwargs['cnn_out_channels']),
                dict(layer_no=1, model='CNN', in_channels=1, kernel_size=kwargs['cnn_filter_size'], stride=kwargs['cnn_stride'], out_channels=kwargs['cnn_out_channels']),
                dict(layer_no=2, model='Transformer', nhead=kwargs['grid_tf_head'], num_encoder_layers=1, num_decoder_layers=1),
                dict(layer_no=3, model='Linear', out_features= num_stations * output_channels)
            ]}
        else:
            # Model configuration for Graph-based architectures (GCN and GAT)
            return {
            'GCN': [
                dict(layer_no=1, model='GCN', out_channels=kwargs['hidden_channels']),
                dict(layer_no=1, model='GCN', out_channels=kwargs['hidden_channels']),
                dict(layer_no=2, model='Transformer', d_model=kwargs['hidden_channels'] * 2, nhead=kwargs['graph_tf_nhead'], num_encoder_layers=1, num_decoder_layers=1),
                dict(layer_no=3, model='Linear', in_features=kwargs['hidden_channels'] * 2, out_features=num_stations * output_channels)
            ],
            'GAT': [
                dict(layer_no=1, model='GAT', heads=graph_layer_heads, out_channels=kwargs['hidden_channels']),
                dict(layer_no=1, model='GAT', heads=graph_layer_heads, out_channels=kwargs['hidden_channels']),
                dict(layer_no=2, model='Transformer', d_model=kwargs['hidden_channels'] * graph_layer_heads * 2, nhead=kwargs['graph_tf_nhead'], num_encoder_layers=1, num_decoder_layers=1),
                dict(layer_no=3, model='Linear', in_features=kwargs['hidden_channels'] * graph_layer_heads * 2, out_features=num_stations * output_channels)
            ]
                }
            