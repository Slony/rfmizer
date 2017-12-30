#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright 2016-2018 Google Inc. All Rights Reserved.

"""RFM segmentation and prediction tool.

RFMizer is a Python script that takes a complete log of users' orders exported
from CRM system and outputs user ID to RFMxyz segments mapping and RFMxyz
segments to bid multipliers mapping.

Usage example:

  python rfmizer.py config.yaml
"""


__author__ = 'aprikhodko@google.com (Alexander Prikhodko)'


import argparse
import csv
import datetime
import logging
import os
import pprint
import re
import sys
from builtins import dict  # pylint: disable=redefined-builtin
from builtins import range  # pylint: disable=redefined-builtin
import yaml


def load_config(filename):
  """Reads configuration settings from YAML file and returns config dict.

  Args:
    filename: Name of configuration file.

  Returns:
    Dict with configuration settings values.
  """
  with open(filename, 'r') as f:
    conf = yaml.load(f)
  logging.info('conf = %s', pprint.pformat(conf))
  return conf


def parse_date(s):
  """Parses date string from input CSV file.

  Args:
    s: date in string format.

  Returns:
    Date instance or None if string can't be parsed.
  """
  pattern = r'(\d{4})\D(\d\d?)\D(\d\d?)|(\d\d?)\D(\d\d?)\D(\d{4})'
  match = re.search(pattern, s)
  if not match:
    return None
  else:
    groups = match.groups()
  if groups[0] is not None:
    date_str = '%s-%s-%s' % (groups[0], groups[1], groups[2])
  else:
    date_str = '%s-%s-%s' % (groups[5], groups[4], groups[3])
  return datetime.datetime.strptime(date_str, '%Y-%m-%d')


def parse_value(s):
  """Parses order value string from input CSV file.

  Args:
    s: order value in string format.

  Returns:
    Floating point number or None if string can't be parsed.
  """
  pattern = r'-?\d*[.,]?\d+'
  match = re.search(pattern, s)
  if not match:
    return None
  else:
    value_str = match.group().replace(',', '.')
  return float(value_str)


class Rfmizer(object):
  """Instances of this class implement the RFMizer functionality.
  """
  ORDER_COLUMNS = set(('user_id', 'order_date', 'order_value'))
  RFM_DIMENSIONS = set(('recency', 'frequency', 'monetary'))

  def __init__(self, conf):
    """Initialises RFMizer with configuration settings and initial values.

    Args:
      conf: dict with config settings.
    """
    self.conf = conf
    self.max_date = parse_date('2000-01-01')
    self.look_back_delta = datetime.timedelta(
        conf['rfmizer']['look_back_period'])
    self.prediction_delta = datetime.timedelta(
        conf['predictor']['prediction_period'])
    self.borders = {}

  def load_input(self, filename):
    """Reads input data file line by line and fills users dict with data.

    Args:
      filename: name of the file with input data in CSV format.
    """
    self.users = dict()
    with open(filename, 'r') as csv_file:
      rows = csv.reader(csv_file)
      for row in rows:
        order = {}
        dimensions = {}
        for i, column in enumerate(self.conf['input_columns']):
          if column in self.ORDER_COLUMNS:
            order[column] = row[i]
          else:
            dimensions[column] = row[i]

        order_date = parse_date(order['order_date'])
        if not order_date:
          continue
        order_value = parse_value(order['order_value'])
        user_id = order['user_id']
        if user_id not in self.users:
          self.users[user_id] = {'orders': {}, 'max_date': order_date,
                                 'dimensions': dimensions}
        if order_date not in self.users[user_id]['orders']:
          self.users[user_id]['orders'][order_date] = None
        if order_value:
          if self.users[user_id]['orders'][order_date] is None:
            self.users[user_id]['orders'][order_date] = order_value
          else:
            self.users[user_id]['orders'][order_date] += order_value
        if order_date > self.users[user_id]['max_date']:
          self.users[user_id]['max_date'] = order_date
          self.users[user_id]['dimensions'] = dimensions
        if order_date > self.max_date:
          self.max_date = order_date
    logging.info('max_date = %s', self.max_date.strftime('%Y-%m-%d'))

  def metricize(self, today):
    """Fills users dict elements with calculated RFM values.

    Args:
      today: date considedred as today's date in calculations.
    """
    start = today - self.look_back_delta
    logging.info('Metricizing between dates %s and %s',
                 start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
    future_uids = []
    for uid in self.users:
      user = self.users[uid]
      orders = []
      max_date = parse_date('2000-01-01')
      min_date = parse_date('2200-01-01')
      for d in user['orders']:
        if start <= d and d <= today:
          orders.append(user['orders'][d])
          if d > max_date:
            max_date = d
        if d < min_date:
          min_date = d
      orders_count = len(orders)
      if orders_count == 0:
        if min_date > today:
          future_uids.append(uid)
        else:
          user['metrics'] = {'recency': 'stale', 'frequency': 'stale',
                             'monetary': 'stale'}
        continue
      non_zero_orders = [o for o in orders if o is not None]
      non_zero_orders_count = len(non_zero_orders)
      non_zero_orders_sum = sum(non_zero_orders)
      if non_zero_orders_count > 0:
        average_order = non_zero_orders_sum / non_zero_orders_count
      else:
        average_order = None
      days_passed = (max_date - today).days
      user['metrics'] = {'recency': days_passed, 'frequency': orders_count,
                         'monetary': average_order}
    for uid in future_uids:
      del self.users[uid]

  def segmentize(self, dimension):
    """Divide users to segments of a given RFM dimension.

    Args:
      dimension: recency, frequency or monetary.
    """
    by_borders = dimension in self.borders
    if by_borders:
      segments_count = len(self.borders[dimension]) + 1
    else:
      self.borders[dimension] = {}
      segments_count = self.conf['segments_count'][dimension]
    uids = []
    for uid in self.users:
      user = self.users[uid]
      if user['metrics'][dimension] is None:
        user['dimensions'][dimension] = 1
      elif user['metrics'][dimension] == 'stale':
        user['dimensions'][dimension] = 0
      else:
        uids.append(uid)
    uids.sort(key=lambda uid: self.users[uid]['metrics'][dimension])
    segment = 1
    uids_count = len(uids)
    if not by_borders:
      max_i = uids_count / segments_count
      prev_metric = self.users[uids[0]]['metrics'][dimension]
    for i in range(0, uids_count):
      user = self.users[uids[i]]
      metric = user['metrics'][dimension]
      if by_borders:
        if segment < segments_count:
          if metric >= self.borders[dimension][segment]:
            segment += 1
      else:
        if i >= max_i and metric != prev_metric:
          self.borders[dimension][segment] = metric
          segment += 1
          max_i = i + (uids_count - i) / (segments_count - segment + 1)
      prev_metric = metric
      user['dimensions'][dimension] = segment

  def rfmize(self, today=None):
    """Fills users dict with RFM segments calculated for a given today.

    Args:
      today: date of today used in calculations. If no today's date given, then
          this method uses maximum date found in an input file.
    """
    if not today:
      today = self.max_date
    logging.info('Rfmizing with today = %s', today.strftime('%Y-%m-%d'))
    self.metricize(today)
    for dimension in self.RFM_DIMENSIONS:
      self.segmentize(dimension)

  def save_mapping(self):
    """Writes user IDs to segments mapping to an output file."""
    columns = self.conf['rfmizer']['output_columns']
    filename = os.path.join(self.conf['output_path'],
                            '%s_mapping.csv' % self.conf['output_file_prefix'])
    with open(filename, 'w') as f:
      writer = csv.writer(f)
      dimensions = sorted(next(iter(self.users.values()))['dimensions'].keys())
      head = [columns['user_id']] + [columns[d] for d in dimensions]
      writer.writerow(head)
      for uid in self.users:
        user = self.users[uid]
        segments = [ds[1] for ds in sorted(user['dimensions'].items())]
        writer.writerow([uid] + segments)

  def save_borders(self):
    """Writes RFM segmets' borders to an output file."""
    filename = os.path.join(self.conf['output_path'],
                            '%s_borders.csv' % self.conf['output_file_prefix'])
    with open(filename, 'w') as f:
      writer = csv.writer(f)
      writer.writerow(['dimension', 'segment', 'border'])
      for dimension in sorted(self.borders):
        borders = self.borders[dimension]
        for segment in sorted(borders):
          writer.writerow([dimension, segment, borders[segment]])

  def rationize(self):
    """Calculates bid ratios for all micro segments."""
    prediction_date = self.max_date - self.prediction_delta
    self.rfmize(prediction_date)
    segments = {}
    total_orders_value = 0
    for uid in self.users:
      user = self.users[uid]
      segment = tuple(sorted(user['dimensions'].items()))
      orders_value = sum([user['orders'][d] for d in user['orders']
                          if user['orders'][d] and d > prediction_date])
      total_orders_value += orders_value
      if segment not in segments:
        segments[segment] = {
            'users_count': 1,
            'orders_value': orders_value}
      else:
        segments[segment]['users_count'] += 1
        segments[segment]['orders_value'] += orders_value
    total_average_orders_value = total_orders_value / len(self.users)
    self.ratios = {}
    for segment in segments:
      self.ratios[segment] = (
          segments[segment]['orders_value'] /
          segments[segment]['users_count'] /
          total_average_orders_value)
    logging.info('segments = %s', pprint.pformat(segments))
    logging.info('total_orders_value = %f', total_orders_value)
    logging.info('total_average_orders_value = %f', total_average_orders_value)

  def save_ratios(self):
    """Writes micro segments to bid ratios mapping to an output file."""
    filename = os.path.join(self.conf['output_path'],
                            '%s_ratios.csv' % self.conf['output_file_prefix'])
    with open(filename, 'w') as f:
      writer = csv.writer(f)
      dimensions = sorted(next(iter(self.users.values()))['dimensions'].keys())
      head = dimensions + ['bid ratio']
      writer.writerow(head)
      for micro_segment in self.ratios:
        segments = [ds[1] for ds in micro_segment]
        writer.writerow(segments + [self.ratios[micro_segment]])

  def save_output(self):
    """Processes data in users dict and saves result to two output files."""
    self.rfmize()
    self.save_mapping()
    self.save_borders()
    logging.info('borders = %s', pprint.pformat(self.borders))
    self.rationize()
    self.save_ratios()


def main():
  """RFMizer's main function."""
  # Teaching Python2 to use UTF-8 by default.
  if sys.version[0] == '2':
    reload(sys)
    sys.setdefaultencoding('utf8')
  # Command line arguments parsing.
  parser = argparse.ArgumentParser()
  parser.add_argument('config-file', help='configuration file')
  parser.add_argument('input-file', help='input data file')
  parser.add_argument('--log-level',
                      help='logging level, defaults to WARNING',
                      default='WARNING')
  args = vars(parser.parse_args())
  # Setup logging.
  log_level = getattr(logging, args['log_level'].upper(), None)
  logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                      datefmt='%Y-%m-%d %H:%M:%S',
                      level=log_level)
  # Load configuration settings.
  conf = load_config(args['config-file'])
  # Instantiate Rfmizer with loaded configuration settings.
  rfmizer = Rfmizer(conf)
  # Load input data from input file to Rfmizer instance.
  rfmizer.load_input(args['input-file'])
  # Rfmize input data and save results to output files.
  rfmizer.save_output()


if __name__ == '__main__':
  # Launch the main function.
  main()
