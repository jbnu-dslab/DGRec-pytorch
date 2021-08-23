#!/usr/bin/env python
# -*- coding: utf-8 -*-

import torch
from models.DGRec.model import DGRec
from models.DGRec.eval import MyEvaluator
from models.DGRec.batch.minibatch import MinibatchIterator
from tqdm import tqdm
from loguru import logger

class MyTrainer:
    def __init__(self, device):
        self.device = device

    def train_with_hyper_param(self, minibatch, hyper_param, val_minibatch=None):
        device = hyper_param['device']
        epochs = hyper_param['epochs']
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
        model_size = hyper_param['model_size']
        dropout = hyper_param['dropout']
        weight_decay = hyper_param['weight_decay']
        print_every = hyper_param['print_every']
        val_every = hyper_param['val_every']

        model = DGRec(hyper_param, num_layers=2).to(self.device)
        evaluator = MyEvaluator(device=device)
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=400, gamma=0.98)

        pbar = tqdm(range(epochs), position=0, leave=False, desc='epoch')

        batch_len = minibatch.train_batch_len()
        batch_len = int(batch_len)

        patience = 5
        inc = 0
        early_stopping = False
        highest_val_recall = -1.0

        model.train()
        for epoch in pbar:
            minibatch.shuffle()
            for batch in tqdm(range(batch_len), position=1, leave=False, desc='batch'):
                feed_dict = minibatch.next_train_minibatch_feed_dict()
                optimizer.zero_grad()

                loss = model(feed_dict, feed_dict['output_session'])

                loss.backward()
                optimizer.step()
                scheduler.step()

                if (batch % 100) == 0:
                    print('Batch {:03}: {:.4} training loss'.format(batch, loss.item()))

                if (batch % 500) == 0 and val_minibatch is not None:
                    #print(torch.optim.lr_scheduler.StepLR.get_last_lr(scheduler))
                    loss, recall_k, ndcg = evaluator.evaluate(model, val_minibatch, hyper_param, 'val')
                    if(recall_k >= highest_val_recall):
                        pbar.write('Batch {:03}: valid loss: {:.4},  valid recall@20: {:.4},  valid ndcg: {:.4}'
                                   .format(batch, loss, recall_k, ndcg))

                        highest_val_recall = recall_k
                        model.train()
                    else:
                        inc += 1
                if inc >= patience:
                    early_stopping = True
                    break

            if early_stopping:
                print('Early stop at epoch: {}, batch steps: {}'.format(epoch, batch))
                break

            pbar.write('Epoch {:02}: {:.4} training loss'.format(epoch, loss.item()))
            pbar.update()

        pbar.close()

        return model
