from auditory_cortex.Regression import transformer_regression
from auditory_cortex.ridge_regression import RidgeRegression 


import sys
import yaml
from yaml import Loader
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score

# import time
import csv


conf_path = '/scratch/gilbreth/akamsali/Research/Makin/Auditory_Cortex/conf/ridge_conf.yaml'

# conf_path = '/Users/akshita/Documents/Research/Makin/Auditory_Cortex/conf/ridge_conf.yaml'
with open(conf_path, "r") as f:
    manifest = yaml.load(f, Loader=Loader)

data_path = manifest['data_path']
subject = manifest['sub']
output_dir = manifest['output_dir']

# data_path = '/Users/akshita/Documents/Research/Makin/data'
# subject = '200206'
# output_dir = '/Users/akshita/Documents/Research/Makin/Auditory_Cortex'

reg = transformer_regression(data_path, subject)

test_list = np.arange(450,499).tolist()
train_val_list = np.arange(1,450)
# train_list = np.arange(1,450).tolist()
w = 80
sp = 1

num_layers = len(reg.layers)


alphas = [0, 1, 10, 100, 1000, 10000, 100000]

kf = KFold(n_splits=5, shuffle=True)


for train, val in kf.split(train_val_list):
    for l in range(num_layers):
        
        z_vals_test, n_vals_test = reg.get_layer_values_and_spikes(layer=l, win=w, sent_list=test_list)
        
        # test data
        r2t = 0
        r2v = 0
        r2tt = 0
        # start = time.time()
        z_vals_train, n_vals_train = reg.get_layer_values_and_spikes(layer=l, win=80, sent_list=train_val_list[train])
        z_vals_val, n_vals_val = reg.get_layer_values_and_spikes(layer=l, win=80, sent_list=train_val_list[val])
        
        # k_val_train , def_w_train, offset_train, z_vals_train = reg.get_layer_values(layer=l, win=w, sent_list=train_val_list[train])
        # n_vals_train = reg.get_all_channels(def_w=def_w_train, offset=offset_train, k_val=k_val_train, sent_list=train_val_list[train])

        # k_val_val , def_w_val, offset_val, z_vals_val = reg.get_layer_values(layer=l,win=w, sent_list=train_val_list[val])
        # n_vals_val = reg.get_all_channels(def_w=def_w_val, offset=offset_val, k_val=k_val_val, sent_list=train_val_list[val])

        for alpha in alphas:

            ridge_model = Ridge(alpha=alpha)
            ridge_model.fit(z_vals_train, n_vals_train)
            y_hat_train = ridge_model.predict(z_vals_train)
            y_hat_val = ridge_model.predict(z_vals_val)
            y_hat_test = ridge_model.predict(z_vals_test)

            ridge_model = RidgeRegression(alpha=alpha)
            ridge_model.fit(z_vals_train, n_vals_train)
            n_hat_train = ridge_model.predict(z_vals_train)
            n_hat_val = ridge_model.predict(z_vals_val)
            n_hat_test = ridge_model.predict(z_vals_test)

            r2t = reg.cc_norm(n_hat_train, n_vals_train, sp=sp)
            r2v = reg.cc_norm(n_hat_val, n_vals_val, sp=sp)
            r2tt = reg.cc_norm(n_hat_test, n_vals_test, sp=sp)
            
            with open(output_dir + "/" + subject + '_over_alphas' +".csv" ,'a') as f1:
                    writer=csv.writer(f1)
                    row = [subject, l, alpha, r2t, r2v, r2tt, r2_score(n_vals_train, y_hat_train), r2_score(n_vals_val, y_hat_val) ,r2_score(n_vals_test, y_hat_test) ]
                    writer.writerow(row)
                    f1.close()
    
    # with open(output_dir + "/" + subject + '_' + str(int(alpha)) + '_all_layers' +".csv" ,'a') as f2:
    #     writer=csv.writer(f1)
    #     row = [subject, l, alpha, r2t/5, r2v/5, r2tt/5]
    #     writer.writerow(row)
    #     f1.close()