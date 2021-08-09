#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch
from models.mymodel.model import MyModel
from models.mymodel.batch.minibatch import MinibatchIterator
from tqdm import tqdm
from utils import log_param
from loguru import logger


class MyTrainer:
    def __init__(self, device):
        self.device = device

    def train_with_hyper_param(self, data, hyper_param):

        adj_info = data[0]
        latest_per_user_by_time = data[1]
        user_id_map = data[2]
        item_id_map = data[3]
        train_df = data[4]
        valid_df = data[5]
        test_df = data[6]

        epochs = hyper_param['epochs']
        aggregator_type = hyper_param['aggregator_type']
        act = hyper_param['act']
        batch_size = hyper_param['batch_size']
        max_degree = hyper_param['max_degree']
        num_users = hyper_param['num_users']
        num_items = hyper_param['num_items']
        learning_rate = hyper_param['learning_rate']
        hidden_size = hyper_param['hidden_size']
        embedding_size = hyper_param['embedding_size']
        emb_user = hyper_param['emb_user']
        max_length = hyper_param['max_length']
        samples_1 = hyper_param['samples_1']
        samples_2 = hyper_param['samples_2']
        dim1 = hyper_param['dim1']
        dim2 = hyper_param['dim2']
        dropout = hyper_param['dropout']
        weight_decay = hyper_param['weight_decay']
        print_every = hyper_param['print_every']
        val_every = hyper_param['val_every']

        num_items = len(item_id_map) + 1
        num_users = len(user_id_map)
        #print("num_items :", num_items)
        #print("num_users :", num_users)

        '''
        data_loader = torch.utils.data.DataLoader(dataset=train_data,
                                                  batch_size=batch_size,
                                                  shuffle=True,
                                                  drop_last=True)
        '''
        minibatch = MinibatchIterator(adj_info,
                                      latest_per_user_by_time,
                                      [train_df, valid_df, test_df],
                                      batch_size=batch_size,
                                      max_degree=max_degree,
                                      num_nodes=len(user_id_map),
                                      max_length=max_length,
                                      samples_1_2=[samples_1, samples_2])

        '''
        print("input session's len :", len(feed_dict['input_session']))     #200
        print("output_session's len :", len(feed_dict['output_session']))   #200
        print("mask_x's len :", len(feed_dict['mask_x']))   #200
        print("support_nodes_layer1's len :", len(feed_dict['support_nodes_layer1']))   #10000
        print("support_nodes_layer2's len :", len(feed_dict['support_nodes_layer2']))   #1000
        print("support_sessions_layer1's len :", len(feed_dict['support_sessions_layer1'])) #10000
        print("support_sessions_layer2's len :", len(feed_dict['support_sessions_layer2'])) #1000
        print("support_lengths_layer1's len :", len(feed_dict['support_lengths_layer1']))   #10000
        print("support_lengths_layer2's len :", len(feed_dict['support_lengths_layer2']))   #1000
        '''

        minibatch.shuffle() #test code
        feed_dict = minibatch.next_train_minibatch_feed_dict() #test code

        model = MyModel(num_users, num_items, embedding_size, batch_size, samples_1, samples_2, num_layers=2).to(self.device)
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

        model.train()
        pbar = tqdm(range(epochs), position=0, leave=False, desc='epoch')

        loss = model(feed_dict) #test code

        for epoch in pbar:
            avg_loss = 0
            minibatch.shuffle()
            for features, labels in tqdm(data_loader, position=1, leave=False, desc='batch'):
                # send data to a running device (GPU or CPU)
                features = features.view(-1, self.in_dim).to(self.device)
                labels = labels.to(self.device)

                feed_dict = minibatch.next_train_minibatch_feed_dict()

                optimizer.zero_grad()

                loss = model(feed_dict)

                loss.backward()
                optimizer.step()

                avg_loss += loss / total_batches

            pbar.write('Epoch {:02}: {:.4} training loss'.format(epoch, loss.item()))
            pbar.update()

        pbar.close()

        return model