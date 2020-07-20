# work directory
root_workdir = 'workdir'

###############################################################################
size = (32, 100)
mean, std = 0.5, 0.5

train_sensitive = False
train_character = 'abcdefghijklmnopqrstuvwxyz0123456789'
test_sensitive = False
test_character = 'abcdefghijklmnopqrstuvwxyz0123456789'
batch_size = 192
batch_max_length = 25

F = 20
hidden_dim = 256
norm_cfg = dict(type='BN')
num_class = len(train_character) + 1
num_steps = batch_max_length + 1

# 1. deploy

deploy = dict(
    gpu_id='3',
    transform=[
        dict(type='Sensitive', sensitive=train_sensitive),
        dict(type='ColorToGray'),
        dict(type='Resize', size=size),
        dict(type='ToTensor'),
        dict(type='Normalize', mean=mean, std=std),
    ],
    model=dict(
        type='GModel',
        need_text=True,
        body=dict(
            type='GBody',
            pipelines=[
                dict(
                    type='RectificatorComponent',
                    from_layer='input',
                    to_layer='rect',
                    arch=dict(
                        type='TPS_STN',
                        F=F,
                        input_size=size,
                        output_size=size,
                        stn=dict(
                            feature_extractor=dict(
                                encoder=dict(
                                    backbone=dict(
                                        type='GVGG',
                                        layers=[
                                            ('conv', dict(type='ConvModule', in_channels=1, out_channels=64,
                                                          kernel_size=3, stride=1, padding=1, norm_cfg=norm_cfg)),
                                            ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2)),
                                            ('conv', dict(type='ConvModule', in_channels=64, out_channels=128,
                                                          kernel_size=3, stride=1, padding=1, norm_cfg=norm_cfg)),
                                            ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2)),
                                            ('conv', dict(type='ConvModule', in_channels=128, out_channels=256,
                                                          kernel_size=3, stride=1, padding=1, norm_cfg=norm_cfg)),
                                            ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2)),
                                            ('conv', dict(type='ConvModule', in_channels=256, out_channels=512,
                                                          kernel_size=3, stride=1, padding=1, norm_cfg=norm_cfg)),
                                        ],
                                    ),
                                ),
                                collect=dict(type='CollectBlock', from_layer='c3')
                            ),
                            pool=dict(type='AdaptiveAvgPool2d', output_size=1),
                            head=[
                                dict(type='FCModule', in_channels=512, out_channels=256),
                                dict(type='FCModule', in_channels=256, out_channels=F * 2, activation=None)
                            ],
                        ),
                    ),
                ),
                dict(
                    type='FeatureExtractorComponent',
                    from_layer='rect',
                    to_layer='cnn_feat',
                    arch=dict(
                        encoder=dict(
                            backbone=dict(
                                type='GResNet',
                                layers=[
                                    ('conv', dict(type='ConvModule', in_channels=1, out_channels=32, kernel_size=3,
                                                  stride=1, padding=1, norm_cfg=norm_cfg)),
                                    ('conv', dict(type='ConvModule', in_channels=32, out_channels=64, kernel_size=3,
                                                  stride=1, padding=1, norm_cfg=norm_cfg)),
                                    ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2, padding=0)),
                                    ('block', dict(block_name='BasicBlock', planes=128, blocks=1, stride=1)),
                                    ('conv', dict(type='ConvModule', in_channels=128, out_channels=128, kernel_size=3,
                                                  stride=1, padding=1, norm_cfg=norm_cfg)),
                                    ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2, padding=0)),
                                    ('block', dict(block_name='BasicBlock', planes=256, blocks=2, stride=1)),
                                    ('conv', dict(type='ConvModule', in_channels=256, out_channels=256, kernel_size=3,
                                                  stride=1, padding=1, norm_cfg=norm_cfg)),
                                    ('pool', dict(type='MaxPool2d', kernel_size=2, stride=(2, 1), padding=(0, 1))),
                                    ('block', dict(block_name='BasicBlock', planes=512, blocks=5, stride=1)),
                                    ('conv', dict(type='ConvModule', in_channels=512, out_channels=512, kernel_size=3,
                                                  stride=1, padding=1, norm_cfg=norm_cfg)),
                                    ('block', dict(block_name='BasicBlock', planes=512, blocks=3, stride=1)),
                                    ('conv', dict(type='ConvModule', in_channels=512, out_channels=512, kernel_size=2,
                                                  stride=(2, 1), padding=(0, 1), norm_cfg=norm_cfg)),
                                    ('conv', dict(type='ConvModule', in_channels=512, out_channels=512, kernel_size=2,
                                                  stride=1, padding=0, norm_cfg=norm_cfg)),
                                ],
                            ),
                        ),
                        collect=dict(type='CollectBlock', from_layer='c4'),
                    ),
                ),
                dict(
                    type='SequenceEncoderComponent',
                    from_layer='cnn_feat',
                    to_layer='rnn_feat',
                    arch=dict(
                        type='RNN',
                        input_pool=dict(type='AdaptiveAvgPool2d', output_size=(1, None)),
                        layers=[
                            ('rnn',
                             dict(type='LSTM', input_size=512, hidden_size=256, bidirectional=True, batch_first=True)),
                            ('fc', dict(type='Linear', in_features=512, out_features=256)),
                            ('rnn',
                             dict(type='LSTM', input_size=256, hidden_size=256, bidirectional=True, batch_first=True)),
                            ('fc', dict(type='Linear', in_features=512, out_features=256)),
                        ],
                    ),
                ),
            ],
        ),
        head=dict(
            type='AttHead',
            num_class=num_class,
            num_steps=num_steps,
            cell=dict(
                type='LSTMCell',
                input_size=256 + num_class,
                hidden_size=256,
            ),
            input_attention_block=dict(
                type='CellAttentionBlock',
                feat=dict(
                    from_layer='rnn_feat',
                    type='ConvModule',
                    in_channels=256,
                    out_channels=256,
                    kernel_size=1,
                    bias=False,
                    activation=None,
                ),
                hidden=dict(
                    type='ConvModule',
                    in_channels=256,
                    out_channels=256,
                    kernel_size=1,
                    activation=None,
                ),
                fusion_method='add',
                post=dict(
                    type='ConvModule',
                    in_channels=256,
                    out_channels=1,
                    kernel_size=1,
                    bias=False,
                    activation='tanh',
                    order=('act', 'conv', 'norm'),
                ),
                post_activation='softmax',
            ),
            generator=dict(
                type='Linear',
                in_features=256,
                out_features=num_class,
            ),
        ),
    ),
)

###############################################################################
# 2.common

common = dict(
    seed=1111,
    logger=dict(
        handlers=(
            dict(type='StreamHandler', level='INFO'),
            dict(type='FileHandler', level='INFO'),
        ),
    ),
    cudnn_deterministic=False,
    cudnn_benchmark=True,
    converter=dict(
        type='AttnConverter',
        character=train_character,
        batch_max_length=batch_max_length,
    ),
    metric=dict(type='Accuracy'),
)
###############################################################################
data_filter_off = False
train_dataset_params = dict(
    batch_max_length=batch_max_length,
    data_filter_off=data_filter_off,
    character=train_character,
)
test_dataset_params = dict(
    batch_max_length=batch_max_length,
    data_filter_off=data_filter_off,
    character=test_character,
)
data_root = './data/data_lmdb_release/'

# train data
train_root = data_root + 'training/'
## MJ dataset
train_root_mj = train_root + 'MJ/'
mj_folder_names = ['/MJ_test', 'MJ_valid', 'MJ_train']
## ST dataset
train_root_st = train_root + 'ST/'

train_dataset_mj = [dict(type='LmdbDataset', root=train_root_mj + folder_name)
                    for folder_name in mj_folder_names]
train_dataset_st = [dict(type='LmdbDataset', root=train_root_st)]

# valid
valid_root = data_root + 'validation/'
valid_dataset = [dict(type='LmdbDataset',
                      root=valid_root,
                      **test_dataset_params)
                 ]

# test dataset
test_root = data_root + 'evaluation/'
test_folder_names = ['CUTE80', 'IC03_867', 'IC13_1015', 'IC15_2077',
                     'IIIT5k_3000', 'SVT', 'SVTP']
test_dataset = [dict(type='LmdbDataset', root=test_root + f_name,
                     **test_dataset_params) for f_name in test_folder_names]

###############################################################################
# 3. test
test = dict(
    data=dict(
        dataloader=dict(
            type='TestDataloader',
            batch_size=batch_size,
            num_workers=4,
            shuffle=False,
        ),
        dataset=test_dataset,
        transform=deploy['transform'],
    ),
    postprocess_cfg=dict(
        sensitive=test_sensitive,
        character=test_character,
    ),
)

###############################################################################
# train transforms
train_transforms = [
    dict(type='Sensitive', sensitive=train_sensitive),
    dict(type='ColorToGray'),
    dict(type='Resize', size=size),
    dict(type='ToTensor'),
    dict(type='Normalize', mean=mean, std=std),
]


niter_per_epoch = int(55000 * 256 / batch_size)
max_iterations = 300000
milestones = [150000, 250000]

# 4. train
train = dict(
    data=dict(
        train=dict(
            dataloader=dict(
                type='BatchBalanceDataloader',
                batch_size=batch_size,
                each_batch_ratio=[0.5, 0.5],
                each_usage=[1.0, 1.0],
                shuffle=True,
                num_workers=4,
            ),
            dataset=[
                dict(
                    type='ConcatDatasets',
                    datasets=train_dataset_mj,
                    **train_dataset_params,
                ),
                dict(
                    type='ConcatDatasets',
                    datasets=train_dataset_st,
                    **train_dataset_params,
                ),
            ],
            transform=train_transforms,
        ),
        val=dict(
            dataloader=dict(
                type='TestDataloader',
                batch_size=batch_size,
                num_workers=4,
                shuffle=False,
            ),
            dataset=valid_dataset,
            transform=deploy['transform'],
        ),
    ),
    optimizer=dict(type='Adadelta', lr=1.0, rho=0.95, eps=1e-8),
    criterion=dict(type='CrossEntropyLoss', ignore_index=0),
    lr_scheduler=dict(type='StepLR',
                      niter_per_epoch=100000,
                      max_epochs=3,
                      milestones=milestones,
                      ),
    max_iterations=max_iterations,
    log_interval=10,
    trainval_ratio=2000,
    snapshot_interval=20000,
    save_best=True,
    resume=None,
)