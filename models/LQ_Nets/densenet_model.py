#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: densenet_model.py

import math

import tensorflow as tf
from tensorflow.contrib.layers import variance_scaling_initializer
from tensorpack.models import *
from tensorpack.tfutils.argscope import argscope, get_arg_scope

from MpuSimConv2D import *
from MpuSimFullyConnected import *

GROWTH_RATE = 32
REDUCTION = 0.5

def add_layer(name, l):
    shape = l.get_shape().as_list()
    in_channel = shape[3]
    with tf.variable_scope(name) as scope:
        c = MpuSimConv2D('conv1x1', l, 4*GROWTH_RATE, 1)
        c = BNReLU('bnrelu_2', c)
        c = MpuSimConv2D('conv3x3', c, GROWTH_RATE, 3)
        c = BNReLU('bnrelu_3', c)
        l = tf.concat([c, l], 3)
    return l


def add_transition(name, l):
    shape = l.get_shape().as_list()
    in_channel = shape[1]
    out_channel = math.floor(in_channel * REDUCTION)
    with tf.variable_scope(name) as scope:
        l = MpuSimConv2D('conv1', l, out_channel, 1,
                            stride=1, use_bias=False)
        l = AvgPooling('pool', l, 2)
    return l


def add_dense_block(l, name, N, last=False, first=False):
    with tf.variable_scope(name) as scope:
        if first:
            l = BNReLU('first', l)
        for i in range(N):
            l = add_layer('dense_layer.{}'.format(i), l)
        if not last:
            l = add_transition('transition', l)
    return l


def densenet_backbone(image,
                        activations_datatype_size_byte,
                        weights_datatype_size_byte,
                        results_datatype_size_byte,
                        systolic_array_height,
                        systolic_array_width,
                        accumulator_array_height):
    
    constant_init = tf.constant_initializer(1)
    with argscope(MpuSimConv2D,
                    data_format='NHWC',
                    use_bias=False), \
            argscope([MpuSimConv2D, MpuSimFullyConnected],
                        nl=tf.identity,
                        kernel_initializer=constant_init, 
                        activations_datatype_size_byte=activations_datatype_size_byte, 
                        weights_datatype_size_byte=weights_datatype_size_byte,
                        results_datatype_size_byte=results_datatype_size_byte,
                        systolic_array_height=systolic_array_height,
                        systolic_array_width=systolic_array_width,
                        activation_fifo_depth=8,
                        accumulator_array_height=accumulator_array_height,
                        log_file_output_dir=("/home/kstehle/masters_thesis/"
                                                "tensorpack_models_mpusim/LQ_Nets/"
                                                "mpu_log/densenet_264/width_height_sweep_constant_pe_count"),
                        model_name='densenet_264_sys_arr_h_{}_sys_arr_w_{}_acc_arr_h_{}'.format(systolic_array_height,
                                                                                                systolic_array_width, 
                                                                                                accumulator_array_height)):
        l = MpuSimConv2D('conv1',
                            image,
                            2*GROWTH_RATE,
                            7,
                            stride=2,
                            activation=BNReLU)
        l = MaxPooling('pool1', l, shape=3, stride=2, padding='SAME')
        l = add_dense_block(l, 'block0', 6)
        l = add_dense_block(l, 'block1', 12)
        l = add_dense_block(l, 'block2', 64)
        l = add_dense_block(l, 'block3', 48, last=True)
        l = BNReLU('bnrelu_last', l)
        l = GlobalAvgPooling('gap', l)
        return MpuSimFullyConnected('linear', l, out_dim=1000)



