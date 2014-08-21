from ament_tools import helper


def test_extract_jobs_flags():
    extract_jobs_flags = helper.extract_jobs_flags
    valid_mflags = [
        '-j8 -l8', 'j8 ', '-j', 'j', '-l8', 'l8',
        '-l', 'l', '-j18', ' -j8 l9', '-j1 -l1',
        '--jobs=8', '--jobs 8', '--jobs', '--load-average',
        '--load-average=8', '--load-average 8', '--jobs=8 -l9'
    ]
    results = [
        '-j8 -l8', 'j8', '-j', 'j', '-l8', 'l8',
        '-l', 'l', '-j18', '-j8 l9', '-j1 -l1',
        '--jobs=8', '--jobs 8', '--jobs', '--load-average',
        '--load-average=8', '--load-average 8', '--jobs=8 -l9'
    ]
    for mflag, result in zip(valid_mflags, results):
        match = extract_jobs_flags(mflag)
        assert match == result, "should match '{0}'".format(mflag)
        print('--')
        print("input:    '{0}'".format(mflag))
        print("matched:  '{0}'".format(match))
        print("expected: '{0}'".format(result))
    invalid_mflags = ['', '--jobs= 8', '--jobs8']
    for mflag in invalid_mflags:
        match = extract_jobs_flags(mflag)
        assert match is None, "should not match '{0}'".format(mflag)
