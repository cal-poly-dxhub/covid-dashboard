import pytz
import utility
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

logger = utility.logger

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

DEFAULT_CUTOFF_DATE = "2020-09-14" #Start of Fall 2020

def generate_available_stats(historical):
    start_date = get_first_date() if historical else datetime.strftime(datetime.now(tz=pytz.timezone('US/Pacific')) - relativedelta(days=90), DATE_FORMAT)

    statistics = {
        #current datetime in PST timestamp of statistics
        "updateDateTime": get_current_datetime(),

        #the earliest recorded testing date in the database
        "startDate": start_date,

        #total count of tests for students/employees since first date in database
        "testCounts": get_test_counts(start_date),

        #Students who have tested positive; on/off campus for yesterday, last7, & total
        "positiveStudentCounts": get_positive_student_counts(start_date),

        #positive test results for students; on/off campus for yesterday, last7, & total
        "studentPositiveTestCounts": get_student_positive_test_counts(start_date),

        #current count of self-quarantine(s)/quarantinue(s)-in-place
        "quarantine": get_quarantine_count(),

        #current count of iso rooms available and occupied
        "isoRoomsAvailable": get_room_availability(),

        #statistics including pos tests, total tests, and daily rolling 7-day % of pos tests over all tests administered
        "dailyTestPos": get_daily_test_pos(start_date),

        #daily count of positive student cases
        "dailyOnVsOffCampus": get_daily_on_off_campus(start_date),

        #daily count of symptomatic/asymptomatic positive tests
        "dailySymptVsAsympt": get_daily_sympt_asympt(start_date),

        #daily count of student compliance for on-campus testing requirements
        #"compliance": get_testing_compliance(start_date),
    }
    return statistics


def get_current_datetime():
    now = datetime.now(tz=pytz.timezone('US/Pacific'))
    return datetime.strftime(now, "{0} {1}".format(DATE_FORMAT, TIME_FORMAT))


def get_first_date():
    earliest_date_stmt = "SELECT MIN(Test_Date) AS Test_Date FROM Tests;"

    response = utility.get_response(earliest_date_stmt)
    result = None
    
    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            result = result[0]['Test_Date']
        except:
            logger.error("Unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: start date")
    return result


def get_test_counts(since_date):
    query = """ SELECT  COUNT(CASE WHEN `Type` = 'Student' AND ON_CAMPUS_RESIDENT_FLAG = 'Y' THEN 1 ELSE NULL END) AS onCampusStu,
                        COUNT(CASE WHEN `Type` = 'Student' AND ON_CAMPUS_RESIDENT_FLAG = 'N' THEN 1 ELSE NULL END) AS offCampusStu,
                        COUNT(CASE WHEN `Type` = 'Faculty' OR `Type` = 'Staff' THEN 1 ELSE NULL END) AS employees,
                        COUNT(*) AS Total
                FROM Tests
                WHERE DATEDIFF(Test_Date, DATE('{}')) >= 0;""".format(since_date)
    data = {
        "total": None,
        "employees": None,
        "onCampusStu": None,
        "offCampusStu": None
    }

    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            data['employees'] = sum([record.get('employees') for record in result])
            data['onCampusStu'] = sum([record.get('onCampusStu') for record in result])
            data['offCampusStu'] = sum([record.get('offCampusStu') for record in result])
            data['total'] = sum([record.get('Total') for record in result])
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: testCounts")
    return data


def get_positive_student_counts(since_date):
    '''
        ON_CAMPUS_RESIDENT_FLAG  |  Yesterday  |  Last7  |  Total
        N                        |  -          |  -      |  -
        Y                        |  -          |  -      |  -
    '''
    query = """ SELECT  ON_CAMPUS_RESIDENT_FLAG,
                        COUNT(CASE WHEN Total > 0 THEN 1 ELSE NULL END) AS Total,
                        COUNT(CASE WHEN Last7a > 0 AND Last7b = 0 THEN 1 ELSE NULL END) AS Last7,
                        COUNT(CASE WHEN Last1a > 0 AND Last1b = 0 THEN 1 ELSE NULL END) AS Yesterday
                FROM (
                    SELECT  ON_CAMPUS_RESIDENT_FLAG,
                            GUID,
                            COUNT(1) AS Total,
                            COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 7 THEN 1 ELSE NULL END) AS Last7a,
                            COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) > 7
                                AND DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 90 THEN 1 ELSE NULL END
                            ) AS Last7b,
                            COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 1 THEN 1 ELSE NULL END) AS Last1a,
                            COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) > 1
                                AND DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 90 THEN 1 ELSE NULL END
                            ) AS Last1b
                    FROM Tests
                    WHERE `Type` = 'Student'
                        AND Result = 'Detected'
                        AND Test_Date < DATE(CONVERT_TZ(NOW(),'+00:00','-8:00'))
                        AND Test_Date >= '{0}'
                    GROUP BY ON_CAMPUS_RESIDENT_FLAG, GUID
                ) AS a
                GROUP BY ON_CAMPUS_RESIDENT_FLAG
                ORDER BY ON_CAMPUS_RESIDENT_FLAG ASC;""".format(since_date)
    data = {
        "onCampus": {
            "Yesterday": None,
            "Last7": None,
            "Total": None,
        },
        "offCampus": {
            "Yesterday": None,
            "Last7": None,
            "Total": None,
        }
    }

    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            for record in result:
                if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'Y':
                    data['onCampus']['Yesterday'] = record.get('Yesterday')
                    data['onCampus']['Last7'] = record.get('Last7')
                    data['onCampus']['Total'] = record.get('Total')
                
                if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'N':
                    data['offCampus']['Yesterday'] = record.get('Yesterday')
                    data['offCampus']['Last7'] = record.get('Last7')
                    data['offCampus']['Total'] = record.get('Total')

        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: positiveStudentCounts")
    return data


def get_student_positive_test_counts(since_date):
    '''
        ON_CAMPUS_RESIDENT_FLAG  |  Yesterday  |  Last7  |  Total
        N                        |  -          |  -      |  -
        Y                        |  -          |  -      |  -
    '''
    query = """ SELECT  ON_CAMPUS_RESIDENT_FLAG,
                        COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 1 THEN 1 ELSE NULL END) AS Yesterday,
                        COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) <= 7 THEN 1 ELSE NULL END) AS Last7,
                        COUNT(1) AS Total
                FROM Tests
                WHERE `Type` = 'Student'
                    AND Result = 'Detected'
                    AND Test_Date < DATE(CONVERT_TZ(NOW(),'+00:00','-8:00'))
                    AND Test_Date >= '{0}'
                GROUP BY ON_CAMPUS_RESIDENT_FLAG
                ORDER BY ON_CAMPUS_RESIDENT_FLAG ASC;""".format(since_date)
    data = {
        "onCampus": {
            "Yesterday": None,
            "Last7": None,
            "Total": None,
        },
        "offCampus": {
            "Yesterday": None,
            "Last7": None,
            "Total": None,
        }
    }

    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            for record in result:
                if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'Y':
                    data['onCampus']['Yesterday'] = record.get('Yesterday')
                    data['onCampus']['Last7'] = record.get('Last7')
                    data['onCampus']['Total'] = record.get('Total')
                
                if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'N':
                    data['offCampus']['Yesterday'] = record.get('Yesterday')
                    data['offCampus']['Last7'] = record.get('Last7')
                    data['offCampus']['Total'] = record.get('Total')

        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: studentPositiveTestCounts")
    return data


def get_quarantine_count():
    data = {
        "selfQuarantine": None,
        "quarantineInPlace": None,
        "isolation": None
    }

    selfQ = 0
    qInPlace = 0
    isolation = 0

    try:
        table_items = utility.get_table_items('cases')
    except:
        logger.error("cases table could not be processed.")
        return data
        
    for case in table_items:
        #disregard tickets meeting any of the below conditions
        if (case.get('On Campus Resident') != 'Y' or
            case.get('Close Out Reason') in ["Deleted"] or
            case.get('Pass Type') in ["Green (Clear for Daily Screener)"] or
            case.get('I/Q/QiP Housing Location') in ["On-Campus Resident who moved home"]):
            continue

        if case.get('Reason for Hold') == "Public Health mandated Quarantine in Place":
            qInPlace += 1
        elif case.get('Reason for Hold') == "Public Health mandated Quarantine":
            selfQ += 1
        elif case.get('Reason for Hold') == "Public Health mandated Isolation":
            isolation += 1
    
    data['selfQuarantine'] = selfQ
    data['quarantineInPlace'] = qInPlace
    data['isolation'] = isolation

    return data


def get_room_availability():
    data = {
        "total": None,
        "occupied": None
    }
    total = 0
    occupied = 0

    try:
        table_items = utility.get_table_items('iso_room')
    except:
        logger.error("iso_room table could not be processed.")
        return data
        
    for room in table_items:
        #disclude closed tickets from iso room count
        if room.get('ticketStatus') != "Closed":
            total += 1
            if room.get('roomStatus') == "Assigned / Occupied":
                occupied += 1
    data['total'] = total
    data['occupied'] = occupied

    return data


def get_daily_test_pos(since_date):
    #definitions
    positive_test = "Result = 'Detected'"
    valid_test = "Result NOT IN ('Inconclusive', 'Invalid', 'TNP')"
    rolling_avg = 7 #days

    '''
        Test_Date   |   positiveTests   |   dailyTests
        2021-01-04  |       2           |       28
        2021-01-05  |       0           |       17
            ...     |       ...         |       ...
    '''
    query = """ SELECT  Test_Date,
                        COUNT(CASE WHEN {0} THEN 1 ELSE NULL END) AS positiveTests,
                        COUNT(CASE WHEN {1} THEN 1 ELSE NULL END) AS validTests,
                        COUNT(*) AS performedTests
                FROM Tests
                WHERE Test_Date >= DATE_SUB('{2}', INTERVAL {3} DAY)
                GROUP BY Test_Date
                ORDER BY Test_Date ASC;""".format(positive_test, valid_test, since_date, str(rolling_avg))
    daily_test_pos = {
        "positiveTests": None,
        "performedTests": None,
        "avgPos7Day": None,
        "dates": None
    }
    
    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #include historical data for rolling average to remain accurate
            start_date -= timedelta(days=rolling_avg)
            
            #creates a complete list of dates from start_date to today PST
            daily_test_pos['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days)]
            
            #scale validTests, 'performedTests' and 'positiveTests' to the size of 'dates' by filling in gaps with 0s
            validTests = [result['validTests'].get(date) or 0 for date in daily_test_pos['dates']]

            daily_test_pos['performedTests'] = [result['performedTests'].get(date) or 0 for date in daily_test_pos['dates']]
            daily_test_pos['positiveTests'] = [result['positiveTests'].get(date) or 0 for date in daily_test_pos['dates']]

            daily_test_pos['avgPos7Day'] = utility.get_rolling_average( daily_test_pos['dates'],
                                                                rolling_avg,
                                                                daily_test_pos['positiveTests'],
                                                                validTests )
            #disclude historical data before start_date
            for key in daily_test_pos.keys():
                daily_test_pos[key] = daily_test_pos[key][rolling_avg:]
        except Exception as e:
            logger.error("daily tests rolling pos average error: {}".format(str(e)))
            #logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY TESTS")

    return daily_test_pos


def get_daily_on_off_campus(since_date):
    '''
        Test_Date   |   onCampusCases   |   offCampusCases
        2021-01-04  |       3           |       1
        2021-01-05  |       6           |       11
            ...     |       ...         |       ...
    '''
    query = """ SELECT  Test_Date,
                        COUNT(CASE WHEN ON_CAMPUS_RESIDENT_FLAG = 'Y' THEN 1 ELSE NULL END) AS onCampusCases,
                        COUNT(CASE WHEN ON_CAMPUS_RESIDENT_FLAG = 'N' THEN 1 ELSE NULL END) AS offCampusCases
                FROM Tests
                WHERE Result = 'Detected'
                    AND `Type` = 'Student'
                    AND Test_Date >= '{}'
                GROUP BY Test_Date
                ORDER BY Test_Date ASC;""".format(since_date)
    student_new_cases = {
        "onCampusCases": None,
        "offCampusCases": None,
        "dates": None
    }

    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #creates a complete list of dates from start_date to today PST
            student_new_cases['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days)]
            
            #scale 'onCampusCases' and 'offCampusCases' to the size of 'dates' by filling in gaps with 0s
            student_new_cases['onCampusCases'] = [result['onCampusCases'].get(date) or 0 for date in student_new_cases['dates']]
            student_new_cases['offCampusCases'] = [result['offCampusCases'].get(date) or 0 for date in student_new_cases['dates']]
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY POSITIVE STUDENTS")
    return student_new_cases


def get_daily_sympt_asympt(since_date):
    '''
    requirements:
    - Symptomatic cases must be identified with the following string case-sensitive "Symptomatic".
    '''
    query = """ SELECT  Test_Date,
                        COUNT(CASE WHEN Reason NOT LIKE '%Symptomatic%' THEN 1 ELSE NULL END) AS asymptCases,
                        COUNT(CASE WHEN Reason LIKE '%Symptomatic%' THEN 1 ELSE NULL END) AS symptCases
                FROM Tests
                WHERE `Type` = 'Student'
                    AND Result = 'Detected'
                    AND Test_Date >= '{}'
                GROUP BY Test_Date
                ORDER BY Test_Date ASC;""".format(since_date)
    sympt_vs_asympt = {
        "symptCases": None,
        "asymptCases": None,
        "dates": None
    }

    response = utility.get_response(query)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #creates a complete list of dates from start_date to today PST
            sympt_vs_asympt['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days)]
            
            #scale 'symptCases' and 'asymptCases' to the size of 'dates' by filling in gaps with 0s
            sympt_vs_asympt['symptCases'] = [result['symptCases'].get(date) or 0 for date in sympt_vs_asympt['dates']]
            sympt_vs_asympt['asymptCases'] = [result['asymptCases'].get(date) or 0 for date in sympt_vs_asympt['dates']]
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY SYMPT/ASYMPT")
    return sympt_vs_asympt


def get_testing_compliance(since_date = None):
    compliance = {
        "dates": None,
        "testedInLast3Days": None,
        "testedInLast6Days": None,
        "totalRequired": None
    }

    try:
        table_items = utility.get_table_items('compliance')
    except:
        logger.error("compliance table could not be processed.")
        return compliance

    #clean up the result
    table_items = sorted(table_items, key=lambda x: x['date'])
    
    #custom cut-off date for smaller dataset
    first_date = datetime.strptime(table_items[0]['date'], DATE_FORMAT)

    if since_date:
        table_items = list(filter(lambda x: datetime.strptime(x['date'], DATE_FORMAT) >= datetime.strptime(since_date, DATE_FORMAT), table_items))

    '''
    CONVERT:
    [{date, totalRequired, testedInlast3Days, testedInLast6Days}, ...]
    
    TO:
    {
        "totalRequired": {date1: X, date2: Y,...},
        "testedInLast3Days": {date1: X, date2: Y,...},
        "testedInLast6Days": {date1: X, date2: Y,...}
    }
    '''

    converted_date_map = {
        "totalRequired": {},
        "testedInLast3Days": {},
        "testedInLast6Days": {}
    }

    for record in table_items:
        converted_date_map['totalRequired'][record['date']] = int(record['totalRequired'])
        converted_date_map['testedInLast3Days'][record['date']] = int(record['testedInLast3Days'])
        converted_date_map['testedInLast6Days'][record['date']] = int(record['testedInLast6Days'])

    global_cutoff_date = since_date if since_date else DEFAULT_CUTOFF_DATE
    global_cutoff_date = datetime.strptime(global_cutoff_date, DATE_FORMAT)

    start_date = first_date if first_date > global_cutoff_date else global_cutoff_date

    #start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
    #start_date = datetime.strptime(start_date, DATE_FORMAT)

    compliance['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days + 1)]
    
    compliance['totalRequired'] = [converted_date_map['totalRequired'].get(date) or 0 for date in compliance['dates']]
    testedInLast3Days = [converted_date_map['testedInLast3Days'].get(date) or 0 for date in compliance['dates']]
    testedInLast6Days = [converted_date_map['testedInLast6Days'].get(date) or 0 for date in compliance['dates']]

    compliance['testedInLast3Days'] = [utility.safe_division(testedInLast3Days[i], compliance['totalRequired'][i]) for i in range(len(compliance['totalRequired']))]
    compliance['testedInLast6Days'] = [utility.safe_division(testedInLast3Days[i] + testedInLast6Days[i], compliance['totalRequired'][i]) for i in range(len(compliance['totalRequired']))]

    return compliance
