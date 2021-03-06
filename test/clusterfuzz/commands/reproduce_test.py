"""Test the module for the 'reproduce' command"""
# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import print_function

import json
import os
import mock

from clusterfuzz import common
from clusterfuzz import binary_providers
from clusterfuzz.commands import reproduce
from test import helpers


class MaybeWarnUnreproducible(helpers.ExtendedTestCase):
  """Test maybe_warn_unreproducible."""

  def test_warn(self):
    """Test warn."""
    self.assertTrue(reproduce.maybe_warn_unreproducible(
        mock.Mock(reproducible=False)))

  def test_not_warn(self):
    """Test warn."""
    self.assertIsNone(reproduce.maybe_warn_unreproducible(
        mock.Mock(reproducible=True)))


class ExecuteTest(helpers.ExtendedTestCase):
  """Test execute."""

  def setUp(self):
    self.chrome_src = '/usr/local/google/home/user/repos/chromium/src'
    self.mock_os_environment({'V8_SRC': '/v8/src', 'CHROME_SRC': '/pdf/src'})
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_testcase_info',
        'clusterfuzz.testcase.Testcase',
        'clusterfuzz.commands.reproduce.ensure_goma',
        'clusterfuzz.binary_providers.DownloadedBinary',
        'clusterfuzz.binary_providers.V8Builder',
        'clusterfuzz.binary_providers.ChromiumBuilder',
        'clusterfuzz.commands.reproduce.reproduce_crash'])
    self.response = {
        'id': 1234,
        'crash_type': 'Bad Crash',
        'crash_state': ['halted'],
        'crash_revision': '123456',
        'metadata': {'build_url': 'chrome_build_url'},
        'crash_stacktrace': {'lines': ['Line 1', 'Line 2']}}
    self.mock.get_testcase_info.return_value = self.response
    self.mock.ensure_goma.return_value = '/goma/dir'

  def test_unsupported_job(self):
    """Tests to ensure an exception is thrown with an unsupported job type."""

    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='fuzzlibber_xunil')
    self.mock.Testcase.return_value = testcase
    with self.assertRaises(common.JobTypeNotSupportedError):
      reproduce.execute('1234', False, 'standalone')

  def test_download_no_defined_binary(self):
    """Test what happens when no binary name is defined."""
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_binary_definition'])
    self.mock.get_binary_definition.return_value = mock.Mock(
        binary_name=None, sanitizer='ASAN')
    self.mock.DownloadedBinary.return_value = mock.Mock(symbolizer_path=(
        '/path/to/symbolizer'))
    self.mock.DownloadedBinary.return_value.get_binary_path.return_value = (
        '/path/to/binary')
    stacktrace = [
        {'content': 'incorrect'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --args --arg2 '
                     '/path/to/testcase')}]
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         stacktrace_lines=stacktrace, reproducible=True)
    self.mock.Testcase.return_value = testcase
    reproduce.execute('1234', False, 'download')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_exact_calls(self.mock.ensure_goma, [mock.call()])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(
        self.mock.DownloadedBinary.return_value.get_binary_path,
        [mock.call()])
    self.assert_exact_calls(self.mock.DownloadedBinary,
                            [mock.call(1234, 'chrome_build_url', 'binary')])
    self.assert_exact_calls(self.mock.reproduce_crash,
                            [mock.call('/path/to/binary', '/path/to/symbolizer',
                                       testcase, 'ASAN')])

  def test_grab_data_with_download(self):
    """Ensures all method calls are made correctly when downloading."""
    self.mock.DownloadedBinary.return_value = mock.Mock(symbolizer_path=(
        '/path/to/symbolizer'))
    self.mock.DownloadedBinary.return_value.get_binary_path.return_value = (
        '/path/to/binary')
    stacktrace = [
        {'content': 'incorrect'}, {'content': '[Environment] A = b'},
        {'content': ('Running command: path/to/binary --args --arg2 '
                     '/path/to/testcase')}]
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         stacktrace_lines=stacktrace, reproducible=True)
    self.mock.Testcase.return_value = testcase
    reproduce.execute('1234', False, 'download')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_exact_calls(self.mock.ensure_goma, [mock.call()])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(
        self.mock.DownloadedBinary.return_value.get_binary_path,
        [mock.call()])
    self.assert_exact_calls(self.mock.DownloadedBinary,
                            [mock.call(1234, 'chrome_build_url', 'd8')])
    self.assert_exact_calls(self.mock.reproduce_crash,
                            [mock.call('/path/to/binary', '/path/to/symbolizer',
                                       testcase, 'ASAN')])

  def test_grab_data_standalone(self):
    """Ensures all method calls are made correctly when building locally."""

    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.get_binary_definition'])
    self.mock.get_binary_definition.return_value = mock.Mock(
        kwargs={}, source_var='V8_SRC', sanitizer='ASAN')
    (self.mock.get_binary_definition.return_value.builder.return_value
     .get_binary_path.return_value) = '/path/to/binary'
    (self.mock.get_binary_definition.return_value.builder.return_value
     .symbolizer_path) = '/path/to/symbolizer'
    testcase = mock.Mock(id=1234, build_url='chrome_build_url',
                         revision=123456, job_type='linux_asan_d8',
                         reproducible=True)
    self.mock.Testcase.return_value = testcase
    reproduce.execute('1234', False, 'standalone')

    self.assert_exact_calls(self.mock.get_testcase_info, [mock.call('1234')])
    self.assert_exact_calls(self.mock.ensure_goma, [mock.call()])
    self.assert_exact_calls(self.mock.Testcase, [mock.call(self.response)])
    self.assert_exact_calls(
        (self.mock.get_binary_definition.return_value.builder.return_value
         .get_binary_path), [mock.call()])
    self.assert_exact_calls(
        self.mock.get_binary_definition.return_value.builder, [
            mock.call(testcase, self.mock.get_binary_definition.return_value,
                      False, '/goma/dir')])
    self.assert_exact_calls(self.mock.reproduce_crash, [
        mock.call('/path/to/binary', '/path/to/symbolizer', testcase,
                  'ASAN')])


class GetTestcaseInfoTest(helpers.ExtendedTestCase):
  """Test get_testcase_info."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.get_stored_auth_header',
        'clusterfuzz.common.store_auth_header',
        'clusterfuzz.commands.reproduce.get_verification_header',
        'urlfetch.fetch'])

  def test_correct_stored_authorization(self):
    """Ensures that the testcase info is returned when stored auth is correct"""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=200,
        body=json.dumps(response_dict),
        headers=response_headers)

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assert_exact_calls(self.mock.fetch, [mock.call(
        url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
        headers={'Authorization': 'Bearer 12345'})])
    self.assertEqual(response, response_dict)

  def test_incorrect_stored_header(self):
    """Tests when the header is stored, but has expired/is invalid."""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.fetch.side_effect = [
        mock.Mock(status=401),
        mock.Mock(status=200,
                  body=json.dumps(response_dict),
                  headers=response_headers)]
    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.get_verification_header, [mock.call()])
    self.assert_exact_calls(self.mock.fetch, [
        mock.call(
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assertEqual(response, response_dict)


  def test_correct_verification_auth(self):
    """Tests grabbing testcase info when the local header is invalid."""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'id': '12345',
        'crash_type': 'Bad Crash',
        'crash_state': ['Halted']}

    self.mock.get_stored_auth_header.return_value = None
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=200,
        body=json.dumps(response_dict),
        headers=response_headers)

    response = reproduce.get_testcase_info('12345')

    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.get_verification_header, [mock.call()])
    self.assert_exact_calls(self.mock.store_auth_header, [
        mock.call('Bearer 12345')])
    self.assert_exact_calls(self.mock.fetch, [mock.call(
        headers={'Authorization': 'VerificationCode 12345'},
        url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])
    self.assertEqual(response, response_dict)

  def test_incorrect_authorization(self):
    """Ensures that when auth is incorrect the right exception is thrown"""

    response_headers = {'x-clusterfuzz-authorization': 'Bearer 12345'}
    response_dict = {
        'status': 401,
        'type': 'UnauthorizedException',
        'message': {
            'Invalid verification code (12345)': {
                'error': 'invalid_grant',
                'error_description': 'Bad Request'}},
        'params': {
            'testcaseId': ['1234']},
        'email': 'test@email.com'}

    self.mock.get_stored_auth_header.return_value = 'Bearer 12345'
    self.mock.get_verification_header.return_value = 'VerificationCode 12345'
    self.mock.fetch.return_value = mock.Mock(
        status=401,
        body=json.dumps(response_dict),
        headers=response_headers)

    with self.assertRaises(common.ClusterfuzzAuthError) as cm:
      reproduce.get_testcase_info('12345')
    self.assertIn('Invalid verification code (12345)', cm.exception.message)
    self.assert_exact_calls(self.mock.fetch, [
        mock.call(
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345',
            headers={'Authorization': 'Bearer 12345'}),
        mock.call(
            headers={'Authorization': 'VerificationCode 12345'},
            url=reproduce.CLUSTERFUZZ_TESTCASE_INFO_URL % '12345')])

class GetVerificationHeaderTest(helpers.ExtendedTestCase):
  """Tests the get_verification_header method"""

  def setUp(self):
    helpers.patch(self, [
        'webbrowser.open',
        'clusterfuzz.common.ask'])
    self.mock.ask.return_value = '12345'

  def test_returns_correct_header(self):
    """Tests that the correct token with header is returned."""

    response = reproduce.get_verification_header()

    self.mock.open.assert_has_calls([mock.call(
        reproduce.GOOGLE_OAUTH_URL,
        new=1,
        autoraise=True)])
    self.assertEqual(response, 'VerificationCode 12345')


class EnsureGomaTest(helpers.ExtendedTestCase):
  """Tests the ensure_goma method."""

  def setUp(self):
    self.setup_fake_filesystem()
    self.mock_os_environment(
        {'GOMA_DIR': os.path.expanduser(os.path.join('~', 'goma'))})
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_goma_not_installed(self):
    """Tests what happens when GOMA is not installed."""

    with self.assertRaises(common.GomaNotInstalledError) as ex:
      reproduce.ensure_goma()
      self.assertTrue('goma is not installed' in ex.message)

  def test_goma_installed(self):
    """Tests what happens when GOMA is installed."""

    goma_dir = os.path.expanduser(os.path.join('~', 'goma'))
    os.makedirs(goma_dir)
    f = open(os.path.join(goma_dir, 'goma_ctl.py'), 'w')
    f.close()

    result = reproduce.ensure_goma()

    self.assert_exact_calls(self.mock.execute, [
        mock.call(
            'python goma_ctl.py ensure_start', goma_dir,
            environment=os.environ)
    ])
    self.assertEqual(result, goma_dir)


class ReproduceCrashTest(helpers.ExtendedTestCase):
  """Tests the reproduce_crash method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

  def test_reproduce_crash(self):
    """Ensures that the crash reproduction is called correctly."""

    self.mock_os_environment({'ASAN_SYMBOLIZER_PATH': '/llvm/sym/path'})
    testcase_id = 123456
    testcase_file = os.path.expanduser(
        os.path.join('~', '.clusterfuzz', '%s_testcase' % testcase_id,
                     'testcase.js'))
    args = '--turbo --always-opt --random-seed=12345'
    source = '/chrome/source/folder/d8'
    env = {'ASAN_OPTIONS': 'option1=true:option2=false'}
    mocked_testcase = mock.Mock(id=1234, reproduction_args=args,
                                environment=env)
    mocked_testcase.get_testcase_path.return_value = testcase_file

    reproduce.reproduce_crash(source, '/chrome/source/folder/llvm-symbolizer',
                              mocked_testcase, 'ASAN')
    self.assert_exact_calls(self.mock.execute, [mock.call(
        '%s %s %s' % ('/chrome/source/folder/d8',
                      args, testcase_file),
        '/chrome/source/folder', environment={
            'ASAN_SYMBOLIZER_PATH': '/chrome/source/folder/llvm-symbolizer',
            'ASAN_OPTIONS': 'option2=false:option1=true'})])

class SuppressOutputTest(helpers.ExtendedTestCase):
  """Test SuppressOutput."""

  def setUp(self):
    helpers.patch(self, ['os.dup', 'os.open', 'os.close', 'os.dup2'])

    def dup(number):
      if number == 1:
        return 'out'
      elif number == 2:
        return 'err'
    self.mock.dup.side_effect = dup

  def test_suppress(self):
    """Test suppressing output."""
    with reproduce.SuppressOutput():
      pass

    self.assert_exact_calls(self.mock.dup, [mock.call(1), mock.call(2)])
    self.assert_exact_calls(self.mock.close, [mock.call(1), mock.call(2)])
    self.mock.open.assert_called_once_with(os.devnull, os.O_RDWR)
    self.assert_exact_calls(
        self.mock.dup2, [mock.call('out', 1), mock.call('err', 2)])

  def test_exception(self):
    """Test propagate exception."""
    with self.assertRaises(Exception) as cm:
      with reproduce.SuppressOutput():
        raise Exception('test_exc')

    self.assertEqual('test_exc', cm.exception.message)

    self.assert_exact_calls(self.mock.dup, [mock.call(1), mock.call(2)])
    self.assert_exact_calls(self.mock.close, [mock.call(1), mock.call(2)])
    self.mock.open.assert_called_once_with(os.devnull, os.O_RDWR)
    self.assert_exact_calls(
        self.mock.dup2, [mock.call('out', 1), mock.call('err', 2)])


class GetBinaryDefinitionTest(helpers.ExtendedTestCase):
  """Tests getting binary definitions."""

  def test_download_param(self):
    """Tests when the build_param is download"""

    result = reproduce.get_binary_definition('libfuzzer_chrome_msan',
                                             'download')
    self.assertEqual(result.builder, binary_providers.LibfuzzerMsanBuilder)

    with self.assertRaises(common.JobTypeNotSupportedError):
      result = reproduce.get_binary_definition('fuzzlibber_nasm', 'download')

  def test_build_param(self):
    """Tests when build_param is an option that requires building."""

    result = reproduce.get_binary_definition('libfuzzer_chrome_msan',
                                             'chromium')
    self.assertEqual(result.builder, binary_providers.LibfuzzerMsanBuilder)

    with self.assertRaises(common.JobTypeNotSupportedError):
      result = reproduce.get_binary_definition('fuzzlibber_nasm', 'chromium')


class SetUpSymbolizersSuppressionsTest(helpers.ExtendedTestCase):
  """Tests the set_up_symbolizers_suppressions method."""

  def setUp(self):
    helpers.patch(self, ['os.path.dirname'])

  def test_set_up_correct_env(self):
    """Ensures all the setup methods work correctly."""

    self.mock.dirname.return_value = '/parent/dir'
    env = {'UBSAN_OPTIONS': ('external_symbolizer_path=/not/correct/path:'
                             'other_option=1:suppressions=/not/correct/path'),
           'LSAN_OPTIONS': 'other=0:suppressions=not/correct/path:option=1'}
    result = reproduce.set_up_symbolizers_suppressions(
        env, '/path/to/symbolizer', 'UBSAN')
    for i in result:
      if '_OPTIONS' in i:
        result[i] = reproduce.deserialize_sanitizer_options(result[i])
    self.assertEqual(result, {
        'UBSAN_OPTIONS': {
            'external_symbolizer_path': '/path/to/symbolizer',
            'other_option': '1',
            'suppressions': '/parent/dir/suppressions/ubsan_suppressions.txt'},
        'LSAN_OPTIONS': {
            'other': '0',
            'suppressions': '/parent/dir/suppressions/lsan_suppressions.txt',
            'option': '1'},
        'UBSAN_SYMBOLIZER_PATH': '/path/to/symbolizer'})


class SanitizerOptionsSerializerTest(helpers.ExtendedTestCase):
  """Test the serializer & deserializers for sanitizer options."""

  def test_serialize(self):
    in_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
               'option': '1',
               'symbolizer': 'abcde/llvm-symbolizer'}
    out_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
               ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(reproduce.serialize_sanitizer_options(in_dict), out_str)

  def test_deserialize(self):
    out_dict = {'suppressions': '/a/b/c/d/suppresions.txt',
                'option': '1',
                'symbolizer': 'abcde/llvm-symbolizer'}
    in_str = ('suppressions=/a/b/c/d/suppresions.txt:option=1'
              ':symbolizer=abcde/llvm-symbolizer')

    self.assertEqual(reproduce.deserialize_sanitizer_options(in_str), out_dict)
