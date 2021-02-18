import pytz
import utility
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

logger = utility.logger

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"

def generate_available_stats(historical):
    start_date = get_first_date() if historical else datetime.strftime(datetime.now(tz=pytz.timezone('US/Pacific')) - relativedelta(months=3), DATE_FORMAT)

    statistics = {
        #current datetime in PST timestamp of statistics
        "updateDateTime": get_current_datetime(),

        #the earliest recorded testing date in the database
        "startDate": start_date,

        #positive student cases, including positive student cases yesterday
        "totalPositive": get_total_pos_student(start_date),

        #current count of iso rooms available and occupied
        "isoRoomsAvailable": get_room_availability(),

        #total count of positive student cases 'within the last 7 days'
        "totalPositiveLast7": get_pos_stu_prev_days(7),

        #total count of tests for students/employees since first date in database
        "testsSinceStart": get_tests_since(start_date),

        #statistics including pos tests, total tests, and daily rolling 7-day % of pos tests over all tests administered
        "dailyTestPos": get_daily_pos_tests(start_date),

        #daily count of positive student cases
        "studentNewCases": get_pos_student_daily(start_date),

        #daily count of symptomatic/asymptomatic positive tests
        "symptVsAsympt": get_daily_sympt_asympt(start_date),

        #current count of self-quarantine(s)/quarantinue(s)-in-place
        "quarantine": get_quarantine_count(),

        #daily rolling 14-day % of positive cases over all tests administered
        "rollingPosCases": get_rolling_pos(start_date)
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


def get_total_pos_student(since_date = None):
    '''
        ON_CAMPUS_RESIDENT_FLAG     |   Yesterday   |   Total
        N                           |       -       |    -
        Y                           |       -       |    -
    '''
    pos_students_stmt = """ SELECT  ON_CAMPUS_RESIDENT_FLAG,
                                    COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Result_Date) = 1 THEN 1 ELSE NULL END) AS Yesterday,
                                    COUNT(*) AS Total
                            FROM Tests
                            WHERE `Type` = 'Student'
                                AND Result = 'Detected'
                                {}
                            GROUP BY ON_CAMPUS_RESIDENT_FLAG;""".format("AND Test_Date >= '{}'".format(since_date) if since_date else "")
    total_positive = {
        "onCampusStu": None, 
        "onCampusYesterday": None,
        "offCampusStu": None,
        "offCampusYesterday": None
    }

    response = utility.get_response(pos_students_stmt)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            total_positive['onCampusStu'] = sum([record.get('Total') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'Y'])
            total_positive['offCampusStu'] = sum([record.get('Total') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'N'])

            total_positive['onCampusYesterday'] = sum([record.get('Yesterday') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'Y'])
            total_positive['offCampusYesterday'] = sum([record.get('Yesterday') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'N'])
        except:
            logger.error("Unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: TOTAL POS STUDENTS")
    return total_positive


def get_room_availability():
    room_count = {
        "total": None,
        "occupied": None
    }
    total = 0
    occupied = 0

    try:
        table_items = utility.get_table_items('iso_room')
    except:
        logger.error("iso_room table could not be processed.")
        return room_count
        
    for room in table_items:
        #disclude closed tickets from iso room count
        if room.get('ticketStatus') != "Closed":
            total += 1
            if room.get('roomStatus') == "Assigned / Occupied":
                occupied += 1
    room_count['total'] = total
    room_count['occupied'] = occupied

    return room_count


def get_pos_stu_prev_days(days, since_date = None):
    '''
        ON_CAMPUS_RESIDENT_FLAG     |   Total
        N                           |    -
        Y                           |    -
    '''
    pos_student_stmt = """  SELECT  ON_CAMPUS_RESIDENT_FLAG,
                                    COUNT(CASE WHEN DATEDIFF(CONVERT_TZ(NOW(),'+00:00','-8:00'), Test_Date) < {0} THEN 1 ELSE NULL END) AS Total
                            FROM Tests
                            WHERE `Type` = 'Student'
                                AND Result = 'Detected'
                                {1}
                            GROUP BY ON_CAMPUS_RESIDENT_FLAG
                            ORDER BY ON_CAMPUS_RESIDENT_FLAG ASC;""".format(str(days), "AND Test_Date >= '{}'".format(since_date) if since_date else "")
    positive_stu_count = {
        "onCampus": None,
        "offCampusInSlo": None
    }

    response = utility.get_response(pos_student_stmt)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            positive_stu_count['offCampusInSlo'] = sum([record.get('Total') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'N'])
            positive_stu_count['onCampus'] = sum([record.get('Total') for record in result if record.get('ON_CAMPUS_RESIDENT_FLAG') == 'Y'])
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: TOTAL POSITIVE STUDENTS LAST 7 DAYS")
    return positive_stu_count


def get_tests_since(since_date):
    tests_since_stmt = """ SELECT 	COUNT(CASE WHEN `Type` = 'Student' AND ON_CAMPUS_RESIDENT_FLAG = 'Y' THEN 1 ELSE NULL END) AS onCampusStu,
                                    COUNT(CASE WHEN `Type` = 'Student' AND ON_CAMPUS_RESIDENT_FLAG = 'N' THEN 1 ELSE NULL END) AS offCampusStu,
                                    COUNT(CASE WHEN `Type` = 'Faculty' OR `Type` = 'Staff' THEN 1 ELSE NULL END) AS employees,
                                    COUNT(*) AS Total
                                 FROM Tests
                                 WHERE DATEDIFF(Test_Date, DATE('{}')) >= 0;""".format(since_date)
    tests_since = {
        "total": None,
        "employees": None,
        "onCampusStu": None,
        "offCampusStu": None
    }

    response = utility.get_response(tests_since_stmt)

    if response.get('records'):
        try:
            result = utility.generate_map_from_response(response)

            tests_since['employees'] = sum([record.get('employees') for record in result])

            tests_since['onCampusStu'] = sum([record.get('onCampusStu') for record in result])
            tests_since['offCampusStu'] = sum([record.get('offCampusStu') for record in result])
            tests_since['total'] = sum([record.get('Total') for record in result])
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: TESTS SINCE JAN4")
    return tests_since


def get_daily_pos_tests(since_date = None):
    #definitions
    positive_test = "Result = 'Detected'"
    valid_test = "Result NOT IN ('Inconclusive', 'Invalid', 'TNP')"

    '''
        Test_Date   |   positiveTests   |   dailyTests
        2021-01-04  |       2           |       28
        2021-01-05  |       0           |       17
            ...     |       ...         |       ...
    '''
    daily_test_pos_stmt = """  SELECT  Test_Date,
                                        COUNT(CASE WHEN {0} THEN 1 ELSE NULL END) AS positiveTests,
                                        COUNT(CASE WHEN {1} THEN 1 ELSE NULL END) AS validTests,
                                        COUNT(*) AS performedTests
                                FROM Tests
                                {2}
                                GROUP BY Test_Date
                                ORDER BY Test_Date ASC;""".format(positive_test, valid_test, "WHERE Test_Date >= '{}'".format(since_date) if since_date else "")
    daily_test_pos = {
        "positiveTests": None,
        "performedTests": None,
        "avgPos7Day": None,
        "dates": None
    }
    
    response = utility.get_response(daily_test_pos_stmt)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)
            
            #creates a complete list of dates from start_date to today PST
            daily_test_pos['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days + 1)]
            
            #scale validTests, 'performedTests' and 'positiveTests' to the size of 'dates' by filling in gaps with 0s
            validTests = [result['validTests'].get(date) or 0 for date in daily_test_pos['dates']]

            daily_test_pos['performedTests'] = [result['performedTests'].get(date) or 0 for date in daily_test_pos['dates']]
            daily_test_pos['positiveTests'] = [result['positiveTests'].get(date) or 0 for date in daily_test_pos['dates']]

            daily_test_pos['avgPos7Day'] = utility.get_rolling_average( daily_test_pos['dates'],
                                                                7,
                                                                daily_test_pos['positiveTests'],
                                                                validTests )
        except Exception as e:
            logger.error("daily tests rolling pos average error: {}".format(str(e)))
            #logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY TESTS")
    return daily_test_pos


def get_pos_student_daily(since_date = None):
    '''
        Test_Date   |   onCampusCases   |   offCampusCases
        2021-01-04  |       3           |       1
        2021-01-05  |       6           |       11
            ...     |       ...         |       ...
    '''
    pos_student_stmt = """  SELECT  Test_Date,
                                    COUNT(CASE WHEN ON_CAMPUS_RESIDENT_FLAG = 'Y' THEN 1 ELSE NULL END) AS onCampusCases,
                                    COUNT(CASE WHEN ON_CAMPUS_RESIDENT_FLAG = 'N' THEN 1 ELSE NULL END) AS offCampusCases
                            FROM Tests
                            WHERE Result = 'Detected'
                                AND `Type` = 'Student'
                                {}
                            GROUP BY Test_Date
                            ORDER BY Test_Date ASC;""".format("AND Test_Date >= '{}'".format(since_date) if since_date else "")
    student_new_cases = {
        "onCampusCases": None,
        "offCampusCases": None,
        "dates": None
    }

    response = utility.get_response(pos_student_stmt)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #creates a complete list of dates from start_date to today PST
            student_new_cases['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days + 1)]
            
            #scale 'onCampusCases' and 'offCampusCases' to the size of 'dates' by filling in gaps with 0s
            student_new_cases['onCampusCases'] = [result['onCampusCases'].get(date) or 0 for date in student_new_cases['dates']]
            student_new_cases['offCampusCases'] = [result['offCampusCases'].get(date) or 0 for date in student_new_cases['dates']]
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY POSITIVE STUDENTS")
    return student_new_cases

'''
requirements:
- Symptomatic cases must be identified with the following string case-sensitive "Symptomatic".
'''
def get_daily_sympt_asympt(since_date = None):
    sympt_asympt_stmt = """SELECT 	Test_Date,
                                    COUNT(CASE WHEN Reason NOT LIKE '%Symptomatic%' THEN 1 ELSE NULL END) AS asymptCases,
                                    COUNT(CASE WHEN Reason LIKE '%Symptomatic%' THEN 1 ELSE NULL END) AS symptCases
                            FROM Tests
                            WHERE `Type` = 'Student'
                                AND Result = 'Detected'
                                {}
                            GROUP BY Test_Date
                            ORDER BY Test_Date ASC;""".format("AND Test_Date >= '{}'".format(since_date) if since_date else "")
    sympt_vs_asympt = {
        "symptCases": None,
        "asymptCases": None,
        "dates": None
    }

    response = utility.get_response(sympt_asympt_stmt)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #creates a complete list of dates from start_date to today PST
            sympt_vs_asympt['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days + 1)]
            
            #scale 'symptCases' and 'asymptCases' to the size of 'dates' by filling in gaps with 0s
            sympt_vs_asympt['symptCases'] = [result['symptCases'].get(date) or 0 for date in sympt_vs_asympt['dates']]
            sympt_vs_asympt['asymptCases'] = [result['symptCases'].get(date) or 0 for date in sympt_vs_asympt['dates']]
        except:
            logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: DAILY SYMPT/ASYMPT")
    return sympt_vs_asympt


def get_quarantine_count():
    quarantine = {
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
        return quarantine
        
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
    
    quarantine['selfQuarantine'] = selfQ
    quarantine['quarantineInPlace'] = qInPlace
    quarantine['isolation'] = isolation

    return quarantine


def get_rolling_pos(since_date = None):
    '''
        Test_Date   |   posStudents     |   students    | posEmployees  | employees
        2021-01-04  |       3           |       11      |       1       |   5
        2021-01-05  |       6           |       31      |       0       |   3
            ...     |       ...         |       ...     |       ...     |   ...
    '''
    rolling_pos_stmt = """  SELECT 	Test_Date,
                                    COUNT(CASE WHEN `Type` = 'Student' AND Result = 'Detected' THEN 1 ELSE NULL END) AS posStudents,
                                    COUNT(CASE WHEN `Type` = 'Student' THEN 1 ELSE NULL END) AS students,
                                    COUNT(CASE WHEN (`Type` = 'Staff' OR `Type` = 'Faculty') AND Result = 'Detected' THEN 1 ELSE NULL END) AS posEmployees,
                                    COUNT(CASE WHEN (`Type` = 'Staff' OR `Type` = 'Faculty') THEN 1 ELSE NULL END) AS employees
                            FROM Tests
                            {}
                            GROUP BY Test_Date
                            ORDER BY Test_Date ASC;""".format("WHERE Test_Date >= '{}'".format(since_date) if since_date else "")
    rolling_pos_cases = {
        "dates": None,
        "students": None,
        "employees": None
    }

    response = utility.get_response(rolling_pos_stmt)

    if response.get('records'):
        try:
            result = utility.generate_daily_map_from_response("Test_Date", response)

            start_date = since_date if since_date else DEFAULT_CUTOFF_DATE
            start_date = datetime.strptime(start_date, DATE_FORMAT)

            #creates a complete list of dates from start_date to today PST
            rolling_pos_cases['dates'] = [datetime.strftime(start_date + timedelta(days=x), DATE_FORMAT) for x in range((datetime.now(tz=pytz.timezone('US/Pacific')).date() - start_date.date()).days + 1)]
            
            #scale below lists to the size of 'dates' by filling in gaps with 0s
            total_students = [result['students'].get(date) or 0 for date in rolling_pos_cases['dates']]
            pos_students = [result['posStudents'].get(date) or 0 for date in rolling_pos_cases['dates']]

            total_employees = [result['employees'].get(date) or 0 for date in rolling_pos_cases['dates']]
            pos_employees = [result['posEmployees'].get(date) or 0 for date in rolling_pos_cases['dates']]
            
            rolling_pos_cases['students'] = utility.get_rolling_average(rolling_pos_cases['dates'],
                                                                14,
                                                                pos_students,
                                                                total_students)
            rolling_pos_cases['employees'] = utility.get_rolling_average(rolling_pos_cases['dates'],
                                                                14,
                                                                pos_employees,
                                                                total_employees)
        except Exception as e:
            logger.error("rolling positives error: {}".format(str(e)))
            #logger.error("unable to generate map object from response and format: {}".format(response))
    else:
        logger.error("No records info returned: ROLLING POSITIVE")
    return rolling_pos_cases