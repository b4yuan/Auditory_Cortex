import os
import numpy as np
import pandas as pd
import scipy as scp
import pickle
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
from matplotlib.lines import Line2D

# 
from auditory_cortex.analysis.config import *
import auditory_cortex.helpers as helpers
import auditory_cortex.analysis.analysis as analysis
from utils_jgm.tikz_pgf_helpers import tpl_save
from sklearn.decomposition import PCA


axis_lim = {
        6: {0: [-2.5,1.5], 1:[-3,2], 2:[-3.5,1.5], 3:[-3,3],},
        7: {0: [-3,3], 1:[-2,1], 2:[-2,2], 3:[-3,2.5],},
        8: {0: [-3,2.5], 1:[-2,2], 2:[-2,1], 3:[-2,2],},
        9: {0: [-2,1], 1:[-2,2], 2:[-2,2], 3:[-1.5,1.5],},
        10: {0: [-2.5,0.5], 1:[-2,2], 2:[-1.5,1.5], 3:[-2,1.5],},
            }


# creating pca_obj...
saved_results = '/home/ahmedb/projects/Wav2Letter/saved_results/'
pretrained_dir = '/depot/jgmakin/data/auditory_cortex/pretrained_weights/w2l_modified/'
checkpoint_file = 'Wav2letter-epoch=024-val_loss=0.37.ckpt'
checkpoint = os.path.join(pretrained_dir, checkpoint_file)
pca_obj = analysis.PCA_topography()

# setting paramters...
layers = [7]
levels = [0.9]
corr_sign_threshold = 0.3
threshold_factor=100
margin=0.8
normalized = True
exclude_session = 200206.0
if normalized:
    extend_name = '_norm'
else:
    extend_name = ''
for layer in layers:
    for i in range(0, 1):
        for j in range(1,3):
            if i == j or i>j:
                continue
            pc_ind = [i,j]
            # plot_select_pcs(pc_10[pc_ind], spikes, levels=[0.9])
            ax = pca_obj.plot_significant_sessions_best_channel(
                                            layer,
                                            levels = levels,
                                            corr_sign_threshold=corr_sign_threshold,
                                            comps=pc_ind,
                                            normalized=normalized,
                                            margin=1.0,
                                            trim_axis=False,
                                            threshold_factor=threshold_factor,
                                            exclude_session=exclude_session
                                            )
            ax.set_title(f"PCs-{pc_ind}, layer-{layer}, all sessions")
            # plt.xlim(axis_lim[layer][i])
            # plt.ylim(axis_lim[layer][j])
            directory = '../../../saved_results/pcs/NIPS/'
            plt.savefig(os.path.join(directory, f'all_sessions_layer_{layer}_pc{pc_ind}_{extend_name}_excluding_{exclude_session}.jpg'))
            # fig_name = f"all_sessions_layer_{layer}_pc{pc_ind}_{extend_name}.tex"
            # extra_axis_parameters = {
            #     'width=\\figwidth',
            #     'height=\\figheight',
            #     'every x tick label/.append style={rotate=90}',
            #     'xticklabel style={opacity=\\thisXticklabelopacity, align=center}',
            # }
            # tpl_save(
            #     filepath=os.path.join(directory, f'all_sessions_layer_{layer}_pc{pc_ind}_{extend_name}.tex'),
            #     extra_axis_parameters=extra_axis_parameters,
            #     tex_relative_path_to_data='pngs',
            #     extra_lines_start={
            #         '\\providecommand{\\figwidth}{5.7in}%',
            #         '\\providecommand{\\figheight}{2.0in}%',
            #         '\\providecommand{\\thisXticklabelopacity}{1.0}%',
            #     },
            # )
            print(f"Done for layer-{layer}, pc-{pc_ind}...!")
