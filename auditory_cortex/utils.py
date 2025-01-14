import os
import yaml
import pickle

import torch
import torchaudio

import torch.nn as nn

import numpy as np
import pandas as pd

import matplotlib as mpl
from scipy import linalg
import matplotlib.pylab as plt

# local
from auditory_cortex import session_to_coordinates, CMAP_2D
from auditory_cortex import results_dir, aux_dir, saved_corr_dir

# import GPU specific packages...
from auditory_cortex import hpc_cluster
if hpc_cluster:
    import cupy as cp

# from pycolormap_2d import ColorMap2DBremm


# def get_2d_cmap(session, clrm1 ='YlGnBu', clrm2 = 'YlOrRd'):
    
#     cmap1 = mpl.cm.get_cmap(clrm1)
#     cmap2 = mpl.cm.get_cmap(clrm2)    
#     # make a copy of session to coordinates...
#     session_to_coordinates =  helpers.session_to_coordinates.copy()
#     """"maps coordinates to 2d color map."""
#     session = int(float(session))
#     coordinates = session_to_coordinates[session]

#     # mapping to 0-1 range
#     coords_x = (coordinates[0] + 2)/4.0
#     coords_y = (coordinates[1] + 2)/4.0
#     c1 = cmap1(coords_x)
#     c2 = cmap2(coords_y)
#     # c3 = (c1[0],c2[1] ,0.5, c1[3])
#     # c3 = ((c1[0] + c2[0])/2.0,(c1[1] + c2[1])/2.0 ,0.5, c1[3])
#     # c3 = (c1[0],c2[1] ,0.0, c1[3])
#     c3 = (c1[0],c2[1] ,0.0, c1[3])
#     # c3 = cmap_2d(c1, c2)
#     return c3

class SyntheticInputUtils:
    """Contains utility functions for analysis of Synthetic inputs.
    """
    @staticmethod
    def normalize(x):
        """
        ONLY USED FOR VISUALIZING THE SPECTROGRAM...!
        Normalizes the spectrogram (obtained using kaldi transform),
        done to match the spectrogram exactly to the Speec2Text transform
        """
        mean = x.mean(axis=0)
        square_sums = (x ** 2).sum(axis=0)
        x = np.subtract(x, mean)
        var = square_sums / x.shape[0] - mean ** 2
        std = np.sqrt(np.maximum(var, 1e-10))
        x = np.divide(x, std)

        return x
    
    @classmethod
    def get_spectrogram(cls, waveform):
        """Returns spectrogram for the input waveform (ndarray or tensor)"""
        if not torch.is_tensor(waveform):
            waveform = torch.tensor(waveform)
        waveform = torch.atleast_2d(waveform)
            # waveform = waveform.unsqueeze(dim=0)
        waveform = waveform * (2 ** 15)
        spect = torchaudio.compliance.kaldi.fbank(waveform, num_mel_bins=80, window_type='hanning')
        spect = cls.normalize(spect)
        return spect


    @classmethod
    def plot_spect(cls, waveform, cmap='viridis', ax=None):
        """Takes in a waveform (as ndarray or tensor) and plots its 
        spectrogram
        """
        waveform = waveform.squeeze()
        if ax is None:
            fig, ax = plt.subplots()
        if not torch.is_tensor(waveform):
            waveform = torch.tensor(waveform)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(dim=0)
            waveform = cls.get_spectrogram(waveform)
        # waveform = waveform * (2 ** 15)
        # kaldi = torchaudio.compliance.kaldi.fbank(waveform, num_mel_bins=80, window_type='hanning')
        # kaldi = cls.normalize(kaldi)
        x_ticks = np.arange(0, waveform.shape[0], 20)
        data = ax.imshow(waveform.transpose(1,0), cmap=cmap, origin='lower')
        ax.set_xticks(x_ticks, 10*x_ticks)
        ax.set_xlabel('time (ms)')
        ax.set_ylabel('mel filters')
        return data, ax
    
    @classmethod
    def align_add_2_signals(cls, sig1, sig2):
        """Smartly adds (averages) two signals having slight offset,
        by using the cross-correlation to align them before adding. 
        This might have to trim the extra lengths on one side of either 
        signal (depending upon the offset for perfect alignment)."""
        sig1 = sig1.squeeze()
        sig2 = sig2.squeeze()
        cross_corr = np.correlate(sig1, sig2, mode='same')
        # identify the shift for peak of cross-correlation
        if sig1.shape[0] > sig2.shape[0]:
            peak_id = np.argmax(cross_corr) - sig2.shape[0]/2
            sig1 = sig1[:sig2.shape[0]]
        elif sig2.shape[0] > sig1.shape[0]:
            peak_id = np.argmax(cross_corr) - sig1.shape[0]/2
            sig2 = sig2[:sig1.shape[0]]
        else:
            cross_corr = np.correlate(sig1, sig2, mode='same')
            peak_id = np.argmax(cross_corr) - sig1.shape[0]/2
        peak_id = int(peak_id)
        # align and average....
        if peak_id > 0:
            sig1_al = sig1[peak_id:]
            sig2_al = sig2[:-1*peak_id]
            # out_sig = (sig1[peak_id:] + sig2[:-1*peak_id])/2
            # corr = np.corrcoef(sig1[peak_id:], sig2[:-1*peak_id])[0,1]
        elif peak_id < 0:
            sig1_al = sig1[:peak_id]
            sig2_al = sig2[-1*peak_id:]
            
            # out_sig = (sig1[:peak_id] + sig2[-1*peak_id:])/2
            
        else:
            sig1_al = sig1
            sig2_al = sig2
            
            # out_sig = (sig1 + sig2)/2
        
        out_sig = (sig1_al + sig2_al)/2

        fig, ax = plt.subplots(ncols=2)
        cls.plot_spect(sig1_al, cmap='jet', ax=ax[0])
        cls.plot_spect(sig2_al, cmap='jet', ax=ax[1])

        # return the correlation of aligned signals...
        corr = np.corrcoef(sig1_al, sig2_al)[0,1]
                
        return out_sig, corr


    @classmethod
    def align_add_signals(cls, signals_list):
        """Takes in a list of signals, and aligns and combines them
        pairwise, keeps doing it until only one signal is left.
        In short, it align and add first 2, 4 , 8 or any highest 
        possible power of 2.
        For example, given 5 signals, it will only use first 4."""
        while len(signals_list) > 1:
            new_list = []
            m = int(len(signals_list)/2)
            for i in range(m):
                sig1 = signals_list[2*i]
                sig2 = signals_list[2*i + 1]
                new_list.append(cls.align_add_2_signals(sig1, sig2)[0])
            signals_list = new_list
        
        return signals_list[0]
    





class CorrelationUtils:
    """Contains utility functions for correlations analysis.
    """
    def merge_correlation_results(model_name, file_identifiers, idx):
        """
        Args:

            model_name: Name of the pre-trained network
            file_identifiers: List of filename identifiers 
            idx:    id of the file identifier to use for saving the merged results
        """
        # results_dir = '/depot/jgmakin/data/auditory_cortex/correlation_results/cross_validated_correlations'

        corr_dfs = []
        for identifier in file_identifiers:
            filename = f"{model_name}_{identifier}_corr_results.csv"
            file_path = os.path.join(saved_corr_dir, filename)

            corr_dfs.append(pd.read_csv(file_path))

            # remove the file
            os.remove(file_path)

        # save the merged results at the very first filename...
        output_identifer = file_identifiers[idx]    
        filename = f"{model_name}_{output_identifer}_corr_results.csv"
        file_path = os.path.join(saved_corr_dir, filename)

        data = pd.concat(corr_dfs)
        data.to_csv(file_path, index=False)
        print(f"Output saved at: \n {file_path}")

    @staticmethod
    def add_layer_types(model_name, results_identifer):

        # reading layer_types from aux config...
        layer_types = {}
        config_file = os.path.join(aux_dir, f"{model_name}_config.yml")
        with open(config_file, 'r') as f:
            config = yaml.load(f, yaml.FullLoader)

        # config['layers']
        for layer_config in config['layers']:
            layer_types[layer_config['layer_id']] = layer_config['layer_type']

        # reading results directory...
        if results_identifer != '':
            model = f'{model_name}_{results_identifer}'
        else:
            model = model_name 
        filename = f"{model}_corr_results.csv"
        file_path = os.path.join(saved_corr_dir, filename)
        data = pd.read_csv(file_path)
        print(f"reading from {file_path}")

        # remove 'Unnamed' columns
        data = data.loc[:, ~data.columns.str.contains('Unnamed')]

        # add 'layer_type' as a column
        for layer, type in layer_types.items():
            ids = data[data['layer']==layer].index
            data.loc[ids, 'layer_type'] = type

        print("Writing back...!")
        data.to_csv(file_path, index=False)

    @staticmethod
    def copy_normalizer(corr_file):

        filename = f'{corr_file}_corr_results.csv'
        corr_file_path = os.path.join(saved_corr_dir, filename)
        data1 = pd.read_csv(corr_file_path)
        print(f"Reading file from: \n {corr_file_path}")
        # normalizer
        normalizer_file = 'wave2letter_modified_normalizer2_corr_results.csv'
        norm_file_path = os.path.join(saved_corr_dir, normalizer_file)
        data2 = pd.read_csv(norm_file_path)
        print(f"Reading normalizers from: \n {norm_file_path}")

        sessions = data1['session'].unique()
        for session in sessions:
            select_data = data1[data1['session']==session]
            channels = select_data['channel'].unique()
            for ch in channels:
                ids = select_data[select_data['channel'] == ch].index

                norm = data2[(data2['session']==session) &(data2['channel']==ch)]['normalizer'].head(1).item() 

                data1.loc[ids, 'normalizer'] = norm
        
        data1.to_csv(corr_file_path, index=False)
        print(f"Normalizer updated and written back to file: \n {corr_file_path}")



def get_2d_cmap(session):
    cmap_2d = CMAP_2D(range_x=(-2, 2), range_y=(-2, 2))
    coordinates = session_to_coordinates[int(session)]
    color = coordinates_to_color(cmap_2d, coordinates)
    return color


def coordinates_to_color(cmap_2d, coordinates):
    return cmap_2d(coordinates[0], coordinates[1])/255.0


def down_sample(data, k):
    #down samples 'data' by factor 'k' along dim=0 
    n_dim = data.ndim
    if n_dim == 1:
        out = np.zeros(int(np.ceil(data.shape[0]/k)))
    elif n_dim ==2:
        out = np.zeros((int(np.ceil(data.shape[0]/k)), data.shape[1]))
    for i in range(out.shape[0]):
      #Just add the remaining samples at the end...!
      if (i == out.shape[0] -1):
        out[i] = data[k*i:].sum(axis=0)
      else:  
        out[i] = data[k*i:k*(i+1)].sum(axis=0)
    return out

@torch.no_grad()
def poisson_regression_score(model, X, Y):
    # Poisson Prediction with Poisson Score....!
    eta = model(X)
    Y_hat = np.exp(eta)
    # eta = np.log(Y_hat)
    Y_mean = Y.mean()
    score = (Y_hat - Y*np.log(Y_hat)).mean() - (Y_mean - Y*np.log(Y_mean)).mean()
    
    return score.item()

def gaussian_cross_entropy(Y, Y_hat):
    # Gaussian Predictions with Gaussain Loss
    #loss_fn = nn.GaussianNLLLoss(full=True)
    sq_error = (Y - Y_hat)**2
    var = sq_error.sum(axis=0)
    cross_entropy = 0.5*(np.log(2*np.pi) + np.log(var) + 1)
    #cross_entropy = loss_fn(Y.squeeze(), Y_hat.squeeze(), var.squeeze()).item()
    
    return cross_entropy

def poisson_cross_entropy(Y, Y_hat):
    # Poisson predictions with Poisson Loss
    loss_fn = nn.PoissonNLLLoss(log_input=False, full=True)
    cross_entropy = loss_fn(Y, Y_hat).item()
    
    return cross_entropy

def linear_regression_score(Y, Y_hat):
    # using Y_hat 'prediction from linear regression' with Poisson Loss 
    Y_hat[Y_hat <= 0] = 1.0e-5
    Y_mean = Y.mean()
    score = (Y_hat - Y*np.log(Y_hat)).mean() - (Y_mean - Y*np.log(Y_mean)).mean()
    
    return score

def MSE_poisson_predictions(Y, poisson_pred):
    # using Y_hat 'prediction from linear regression' with Poisson Loss 
    Y_hat = np.exp(poisson_pred)
    loss_fn = nn.MSELoss()
    score = loss_fn(Y, Y_hat)
    
    return score

def MSE_Linear_predictions(Y, linear_reg_pred):
    # using Y_hat 'prediction from linear regression' with MSE Loss     
    loss_fn = nn.MSELoss()
    score = loss_fn(Y, linear_reg_pred)
    
    return score

def poiss_regression(x_train, y_train):
    X = torch.tensor(x_train, dtype=torch.float32)
    Y = torch.tensor(y_train, dtype=torch.float32)
    N,d = X.shape
    model = nn.Linear(d, 1, bias=True)
    loss_fn = nn.PoissonNLLLoss(log_input = True, full=True)
    optimizer = torch.optim.Adam(model.parameters())
    
    state = model.state_dict()
    state['bias'] = torch.zeros(1)
    state['weight'] = torch.zeros((1,d))
    model.load_state_dict(state)
    num_epochs = 2000
    criteria = 1e-4
    loss_history = []
    P_scores = []
    
    count = 0
    for i in range(num_epochs):
        Y_hat = model(X)
        loss = loss_fn(Y_hat, Y)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if i >= 50 and (np.linalg.norm(loss_history[-1] - loss.item()) < criteria):
            print(loss_history[-1] - loss.item())
            count += 1
        loss_history.append(loss.item())
        P_scores.append(poisson_regression_score(model, X, Y))
        if count >= 3:
            break
      
    return model, loss_history, P_scores
def write_df_to_disk(df, file_path):
    """
    Takes in any pandas dataframe 'df' and writes as csv file 'file_path',
    appends data to existing file, if it already exists.

    Args:
        df (dataframe): dataframe containing data to write
        file_path (str): name of the file to write to.
    """
    if os.path.isfile(file_path):
        data = pd.read_csv(file_path)
        action = 'appended'
    else:
        data = pd.DataFrame(columns= df.columns)
        action = 'written'
    data = pd.concat([data,df], axis=0, ignore_index=True)
    data.to_csv(file_path, index=False)
    print(f"Dataframe {action} to {file_path}.")

def write_STRF(corr_dict, file_path):
    if os.path.isfile(file_path):
        data = pd.read_csv(file_path)
    else:
        data = pd.DataFrame(columns=['session','channel','bin_width',
                                    'delay','strf_corr'])
    session = corr_dict['session']
    win = corr_dict['win']
    delay = corr_dict['delay']
    ch = np.arange(corr_dict['strf_corr'].shape[0])

    df = pd.DataFrame(np.array([np.ones_like(ch)*int(session),
                                    ch, 
                                    np.ones_like(ch)*win, 
                                    np.ones_like(ch)*delay,
                                    corr_dict['strf_corr'],
                                    ]).transpose(),
                        columns=data.columns
                        )
    data = pd.concat([data,df], axis=0, ignore_index=True)
    data.to_csv(file_path, index=False)
    print(f"Data saved for session: '{session}',\
    bin-width: {win}ms, delay: {delay}ms at file: '{file_path}'")
    return data




def write_to_disk(corr_dict, file_path, normalizer=None):
    """
    | Takes in the 'corr' dict and stores the results
    | at the 'file_path', (concatenates if file already exists)
    | corr: dict of correlation scores
    | win: float
    | delay: float
    | file_path: path of csv file
    """
    if os.path.isfile(file_path):
        data = pd.read_csv(file_path)
    else:
        data = pd.DataFrame(
                columns=[
                    'session','layer','channel','bin_width', 'delay',
                    'train_cc_raw','test_cc_raw', 'normalizer', 'N_sents',
                    'opt_delays'
                    ]
                )
    session = corr_dict['session']
    model_name = corr_dict['model']
    win = corr_dict['win']
    delay = corr_dict['delay']
    ch = np.arange(corr_dict['test_cc_raw'].shape[1])
    layers = np.arange(corr_dict['test_cc_raw'].shape[0])
    N_sents = corr_dict['N_sents']
    layer_ids = corr_dict['layer_ids']
    opt_delays = corr_dict['opt_delays']
    if normalizer is None:
        normalizer = np.zeros_like(ch)
    if opt_delays is None:
        opt_delays = np.zeros((len(layers), len(ch)))
    for layer in layers:
        df = pd.DataFrame(np.array([np.ones_like(ch)*int(session),
                                    np.ones_like(ch)*layer_ids[int(layer)],
                                    ch, 
                                    np.ones_like(ch)*win, 
                                    np.ones_like(ch)*delay,
                                    corr_dict['train_cc_raw'][layer,:],
                                    corr_dict['test_cc_raw'][layer,:],
                                    normalizer,
                                    np.ones_like(ch)*N_sents,
                                    opt_delays[layer,:]
                                    ]).transpose(),
                        columns=data.columns
                        )
        data = pd.concat([data,df], axis=0, ignore_index=True)
    data.to_csv(file_path, index=False)
    print(f"Data saved for model: '{model_name}', session: '{session}',\
    bin-width: {win}ms, delay: {delay}ms at file: '{file_path}'")
    return data

def cc_norm(y, y_hat, sp=1, normalize=False):
    """
    Args:   
        y_hat (ndarray): (n_samples, channels) or (n_samples, channels, repeats) for null dist
        y (ndarray): (n_samples, channels)  
        sp & normalize are redundant...! 
    """
    #check if incoming array is np or cp,
    #and decide which module to use...!
    if type(y).__module__ == np.__name__:
        module = np
    else:
        module = cp
    # if 'normalize' = True, use signal power as factor otherwise use normalize CC formula i.e. 'un-normalized'
    try:
        n_channels = y.shape[1]
    except:
        n_channels=1
        y = module.expand_dims(y,axis=1)
        y_hat = module.expand_dims(y_hat,axis=1)
        
    corr_coeff = module.zeros(y_hat.shape[1:])
    for ch in range(n_channels):
        corr_coeff[ch] = cc_single_channel(y[:,ch],y_hat[:,ch])
    return cp.asnumpy(corr_coeff)

# def cc_norm_cp(y, y_hat, sp=1, normalize=False):
#     """
#     Args:   
#         y_hat (ndarray): (n_samples, channels) or (n_samples, channels, repeats) for null dist
#         y (ndarray): (n_samples, channels)  
#         sp & normalize are redundant...! 
#     """
#     # if 'normalize' = True, use signal power as factor otherwise use normalize CC formula i.e. 'un-normalized'
#     try:
#         n_channels = y.shape[1]
#     except:
#         n_channels=1
#         y = cp.expand_dims(y,axis=1)
#         y_hat = cp.expand_dims(y_hat,axis=1)
        
#     corr_coeff = cp.zeros(y_hat.shape[1:])
#     for ch in range(n_channels):
#         corr_coeff[ch] = cc_single_channel_cp(y[:,ch],y_hat[:,ch])
#     return corr_coeff

# def cc_single_channel_cp(y, y_hat):
#     """
#     computes correlations for the given spikes and predictions 'single channel'

#     Args:   
#         y_hat (ndarray): (n_sampes,) or (n_samples,repeats) spike predictions
#         y (ndarray): (n_samples) actual spikes for single channel 

#     Returns:  
#         ndarray: (1,) or (repeats, ) correlation value or array (for repeats). 
#     """
#     try:
#         y_hat = cp.transpose(y_hat,(1,0))
#     except:
#         y_hat = cp.expand_dims(y_hat, axis=0)
#     return cp.cov(y, y_hat)[0,1:] / (cp.sqrt(cp.var(y)*cp.var(y_hat, axis=1)) + 1.0e-8)

def cc_single_channel(y, y_hat):
    """
    computes correlations for the given spikes and predictions 'single channel'

    Args:   
        y_hat (ndarray): (n_sampes,) or (n_samples,repeats) spike predictions
        y (ndarray): (n_samples) actual spikes for single channel 

    Returns:  
        ndarray: (1,) or (repeats, ) correlation value or array (for repeats). 
    """
    #check if incoming array is np or cp,
    #and decide which module to use...!
    if type(y).__module__ == np.__name__:
        module = np
    else:
        module = cp
    try:
        y_hat = module.transpose(y_hat,(1,0))
    except:
        y_hat = module.expand_dims(y_hat, axis=0)
    return module.cov(y, y_hat)[0,1:] / (module.sqrt(module.var(y)*module.var(y_hat, axis=1)) + 1.0e-8)

# def regression_param(X, y):
#     """
#     Computes the least-square solution to the equation Xz = y,
  
#     Args:
#         X (ndarray): (M,N) left-hand side array
#         y (adarray): (M,) or (M,K) right-hand side array
#     Returns:
#         ndarray: (N,) or (N,K)
#     """
#     B = linalg.lstsq(X, y)[0]
#     return B
def reg(X,y, lmbda=0):

    #check if incoming array is np or cp,
    #and decide which module to use...!
    if type(X).__module__ == np.__name__:
        module = np
    else:
        module = cp
    
    if X.ndim ==2:
        X = module.expand_dims(X,axis=0)
    d = X.shape[2]
    m = X.shape[1]
    a = module.matmul(X.transpose((0,2,1)), X) + m*lmbda*module.eye(d)
    b = module.matmul(X.transpose((0,2,1)), y)
    B = module.linalg.solve(a,b)
    return B.squeeze()

# def reg_cp(X,y, lmbda=0):
#     # takes in cupy arrays and uses gpu...!
#     if X.ndim ==2:
#         X = cp.expand_dims(X,axis=0)
#     d = X.shape[2]
#     m = X.shape[1]
#     I = cp.eye(d)
#     X_T = X.transpose((0,2,1))
#     a = cp.matmul(X_T, X) + m*lmbda*I
#     b = cp.matmul(X_T, y)
#     B = cp.linalg.solve(a,b)
#     return B.squeeze()

# def regression_param(X, y):
#     B = linalg.lstsq(X, y)[0]
#     return B

def predict(X, B):
    """
    Args:
        X (ndarray): (M,N) left-hand side array
        B (ndarray): (N,) or (N,K)
    Returns:
        ndarray: (M,) or (M,K)
    """

    #check if incoming array is np or cp,
    #and decide which module to use...!
    if type(X).__module__ == np.__name__:
        module = np
    else:
        module = cp
    pred = module.matmul(X,B)
    if pred.ndim ==3:
        return pred.transpose(1,2,0) 
    return pred 

# def predict_cp(X, B):
#     """
#     Args:
#         X (ndarray): (M,N) left-hand side array
#         B (ndarray): (N,) or (N,K)
#     Returns:
#         ndarray: (M,) or (M,K)
#     """
#     # pred = X@B
#     # cp.matmul is supposed to be faster...!
#     pred = cp.matmul(X,B)
#     if pred.ndim ==3:
#         return pred.transpose(1,2,0) 
#     return pred 

def fit_and_score(X, y):
    # x_train, y_train, x_test, y_test = train_test_split(X,y, split=0.7)
    # B = reg(x_train,y_train)
    # y_hat = predict(x_test,B)
    # cc = cc_norm(y_hat, y_test)

    B = reg(X,y)
    y_hat = predict(X,B)
    cc = cc_norm(y_hat, y)
    return cc

# def fit_and_score(X, y):
#     B = regression_param(X,y)
#     y_hat = predict(X,B)
#     cc = cc_norm(y_hat, y)
#     return cc

def train_test_split(x,y, split=0.7):
    split = int(x.shape[0]*split)
    return x[0:split], y[0:split], x[split:], y[split:]


def mse_loss(y, y_hat):
    #check if incoming array is np or cp,
    #and decide which module to use...!
    if type(y).__module__ == np.__name__:
        module = np
    else:
        module = cp
    if y.ndim < y_hat.ndim:
        y = module.expand_dims(y, axis=-1)
    return (module.sum((y - y_hat)**2, axis=0))/y_hat.shape[0]

# def mse_loss_cp(y, y_hat):
#     if y.ndim < y_hat.ndim:
#         y = cp.expand_dims(y, axis=-1)
#     return (cp.sum((y - y_hat)**2, axis=0))/y_hat.shape[0]

def inter_trial_corr(spikes, n=1000):
    """Compute distribution of inter-trials correlations.

    Args: 
        spikes (ndarray): (repeats, samples/time, channels)

    Returns:
        trials_corr (ndarray): (n, channels) distribution of inter-trial correlations
    """
    trials_corr = np.zeros((n, spikes.shape[2]))
    for t in range(n):
        trials = np.random.choice(np.arange(0,spikes.shape[0]), size=2, replace=False)
        trials_corr[t] = cc_norm(spikes[trials[0]].squeeze(), spikes[trials[1]].squeeze())

    return trials_corr

def normalize(x):
    # Normalize for spectrogram
    mean = x.mean(axis=0)
    square_sums = (x ** 2).sum(axis=0)
    x = np.subtract(x, mean)
    var = square_sums / x.shape[0] - mean ** 2
    std = np.sqrt(np.maximum(var, 1e-10))
    x = np.divide(x, std)

    return x

def spectrogram(aud):
    waveform = torch.tensor(aud, dtype=torch.float32).unsqueeze(dim=0)
    waveform = waveform * (2 ** 15)
    kaldi = torchaudio.compliance.kaldi.fbank(waveform, num_mel_bins=80, window_type='hanning')
    kaldi = normalize(kaldi)

    return kaldi.transpose(0,1)

def write_optimal_delays(filename, result):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            prev_result = pickle.load(f)
        result['corr'] = np.concatenate([prev_result['corr'], result['corr']], axis=0)
        result['loss'] = np.concatenate([prev_result['loss'], result['loss']], axis=0)
        result['delays'] = np.concatenate([prev_result['delays'], result['delays']], axis=0)
        # temporary change...should be removed after run..!
        # result['delays'] = np.concatenate([np.arange(0,201,10), result['delays']], axis=0)
        

    with open(filename, 'wb') as file:
        pickle.dump(result, file)
