#!/usr/bin/env python
# -*- coding: utf-8 -*-

import numpy as np
import torch
from torch import nn
import dgl
import dgl.ops as F

from torch.nn.utils.rnn import pack_padded_sequence

class GAT(nn.Module):
    def __init__(
        self,
        qry_feats,
        key_feats,
        val_feats,
        batch_norm=False,
        feat_drop=0.0,
    ):
        super().__init__()
        '''
        if batch_norm:
            self.batch_norm_q = nn.BatchNorm1d(qry_feats)
            self.batch_norm_k = nn.BatchNorm1d(key_feats)
        else:
            self.batch_norm_q = None
            self.batch_norm_k = None
        self.feat_drop = nn.Dropout(feat_drop)
        '''
        self.fc = nn.Linear(qry_feats, val_feats, bias=True)

        self.qry_feats = qry_feats

    def forward(self, g, feat_src, feat_dst):
        '''
        if self.batch_norm_q is not None:
            feat_src = self.batch_norm_q(feat_src)
            feat_dst = self.batch_norm_k(feat_dst)
        if self.feat_drop is not None:
            feat_src = self.feat_drop(feat_src)
            feat_dst = self.feat_drop(feat_dst)
        '''
        score = F.u_dot_v(g, feat_src, feat_dst)  # similarity function
        weight = F.edge_softmax(g, score) # softmax
        rst = F.u_mul_e_sum(g, feat_src, weight) # mixture of user's friends' interests
        rst = torch.relu(self.fc(rst)) # obtain representation of each nodes
        return rst

class MyModel(torch.nn.Module):
    def __init__(
        self,
        num_users,
        num_items,
        embedding_dim,
        batch_size,
        sample1,
        sample2,
        num_layers,
        batch_norm=False,
        feat_drop=0.0,
        residual=True,
        **kwargs,
    ):
        super(MyModel, self).__init__()
        self.batch_size = batch_size
        self.sample1 =sample1
        self.sample2 = sample2
        self.num_layers = num_layers
        self.user_embedding = nn.Embedding(num_users,
                                           embedding_dim) #(num_users=26511, embedding_dim=50)
        self.item_embeeding = nn.Embedding(num_items,
                                           embedding_dim,
                                           padding_idx=0) #(num_items=12592, embedding_dim=50)
        self.item_indices = nn.Parameter(torch.arange(1, num_items, dtype=torch.long),
                                         requires_grad=False)
        #self.feat_drop = nn.Dropout(feat_drop) if feat_drop > 0 else None
        self.lstm = nn.LSTM(embedding_dim, embedding_dim, batch_first = True)
        self.W1 = nn.Linear(2 * embedding_dim, embedding_dim, bias=False)

        self.layers = nn.ModuleList()
        input_dim = embedding_dim
        for _ in range(num_layers):
            layer = GAT(
                input_dim,
                input_dim,
                embedding_dim,
                batch_norm=batch_norm,
                feat_drop=feat_drop,
            )
            '''
            if not residual:
                input_dim += embedding_dim
            '''
            self.layers.append(layer)

        #self.residual = residual
        self.W2 = nn.Linear(input_dim + embedding_dim, embedding_dim, bias=False)

    def forward(self, feed_dict):

        #Part-1 : Individual Interest
        input = torch.LongTensor(feed_dict['input_session'][0]) #input.shape : [20]
        emb_seqs = self.item_embeeding(input) #emb_seqs.shape : [20, 50]
        for batch in range(self.batch_size-1):
            input = torch.LongTensor(feed_dict['input_session'][batch+1])
            emb_seq = self.item_embeeding(input)
            emb_seqs = torch.cat((emb_seqs, emb_seq), 0)
        emb_seqs = emb_seqs.view(self.batch_size, 20, 50)

        '''
        if self.feat_drop is not None:
            emb_seqs = self.feat_drop(emb_seqs)
        
        packed_seqs = pack_padded_sequence(emb_seqs,
                                           lens.cpu(),
                                           batch_first=True,
                                           enforce_sorted=False)
        
        _, (hn, _) = self.lstm(packed_seqs)
        '''

        output, (_, _) = self.lstm(emb_seqs) #output.shape : [1, 20, 50]



        #Part-2 : Friends' Interest
        '''
        long-term
        '''
        #print(feed_dict['support_nodes_layer1'])
        #print(feed_dict['support_nodes_layer2'])

        long_input1 = torch.LongTensor(feed_dict['support_nodes_layer1'])
        long_input2 = torch.LongTensor(feed_dict['support_nodes_layer2'])

        long_term1 = self.user_embedding(long_input1) # long_term1.shape : [50, 50]
        long_term2 = self.user_embedding(long_input2) # long_term2.shape : [5, 50]


        long_term = [long_term2, long_term1]



        '''
        short-term
        '''
        #print(feed_dict['support_sessions_layer1'])
        #print(feed_dict['support_sessions_layer2'])
        #print(feed_dict['support_lengths_layer1'])
        #print(feed_dict['support_lengths_layer2'])

        short_input1 = torch.LongTensor(feed_dict['support_sessions_layer1'][0]) #input.shape : [20]
        friend_emb_seqs1 = self.item_embeeding(short_input1) #emb_seqs.shape : [20, 50]
        for batch in range(self.sample1*self.sample2 - 1):
            short_input1 = torch.LongTensor(feed_dict['support_sessions_layer1'][batch+1])
            friend_emb_seq1 = self.item_embeeding(short_input1)
            friend_emb_seqs1 = torch.cat((friend_emb_seqs1, friend_emb_seq1), 0)
        friend_emb_seqs1 = friend_emb_seqs1.view(self.sample1*self.sample2, 20, 50)

        short_term1, (_, _) = self.lstm(friend_emb_seqs1) # short_term1.shape : [50, 20, 50]
        short_term1 = short_term1[:, 0, :] #[50, 20, 50] -> [50, 50]


        short_input2 = torch.LongTensor(feed_dict['support_sessions_layer2'][0])  # input.shape : [20]
        friend_emb_seqs2 = self.item_embeeding(short_input2)  # emb_seqs.shape : [20, 50]
        for batch in range(self.sample2 - 1):
            short_input2 = torch.LongTensor(feed_dict['support_sessions_layer2'][batch + 1])
            friend_emb_seq2 = self.item_embeeding(short_input2)
            friend_emb_seqs2 = torch.cat((friend_emb_seqs2, friend_emb_seq2), 0)
        friend_emb_seqs2 = friend_emb_seqs2.view(self.sample2, 20, 50)

        short_term2, (_, _) = self.lstm(friend_emb_seqs2) # short_term2.shape : [5, 20, 50]
        short_term2 = short_term2[:, 0, :] #[5, 20, 50] -> [5, 50]


        short_term = [short_term2, short_term1]



        '''
        long-term & short-term
        '''
        long_short_term1 = torch.cat((long_term[1], short_term[1]), dim=1) # long_short_term1.shape : [50, 100]
        long_short_term2 = torch.cat((long_term[0], short_term[0]), dim=1) # long_short_term2.shape : [5 ,100]

        long_short_term1 = torch.relu(self.W1(long_short_term1)) # long_short_term1.shape : [50, 50]
        long_short_term2 = torch.relu(self.W1(long_short_term2)) # long_short_term2.shape : [5 ,50]

        long_short_term = [long_short_term1, long_short_term2]



        #Part-3 : Graph-Attention Network

        graphs = dgl.rand_graph(100, 1000)  # create a DGLGraph with 100 nodes and 1000 edges.

        for g, layer in zip(graphs, self.layers):
            feat_src = long_short_term[layer]
            feat_dst = output
            feat = layer(g, feat_src, feat_dst)
            '''
            if self.residual:
                feat = feat_dst + feat
            else:
            '''
            feat = torch.cat((feat_dst, feat), dim=1) # final representation

        sr = self.W2(torch.cat((output, feat), dim=1))
        logits = sr @ self.item_embeeding(self.item_indices).t() #prediction


        return logits
