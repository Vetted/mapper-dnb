#! /usr/bin/env python3

import os
import sys
import argparse
import signal
import time
from datetime import datetime, timedelta
import glob
import csv
import json
import random

#--import the base mapper library and variants
try: 
    import base_mapper
except: 
    print('')
    print('Please export PYTHONPATH=$PYTHONPATH:<path to mapper-base project>')
    print('')
    sys.exit(1)
baseLibrary = base_mapper.base_library(os.path.abspath(base_mapper.__file__).replace('base_mapper.py','base_variants.json'))
if not baseLibrary.initialized:
    sys.exit(1)

#----------------------------------------
def pause(question='PRESS ENTER TO CONTINUE ...'):
    """ pause for debug purposes """
    try: response = input(question)
    except KeyboardInterrupt:
        response = None
        global shutDown
        shutDown = True
    return response

#----------------------------------------
def signal_handler(signal, frame):
    print('USER INTERUPT! Shutting down ... (please wait)')
    global shutDown
    shutDown = True
    return
        
#----------------------------------------
def updateStat(cat1, cat2, example = None):
    if cat1 not in statPack:
        statPack[cat1] = {}
    if cat2 not in statPack[cat1]:
        statPack[cat1][cat2] = {}
        statPack[cat1][cat2]['count'] = 0

    statPack[cat1][cat2]['count'] += 1
    if example:
        if 'examples' not in statPack[cat1][cat2]:
            statPack[cat1][cat2]['examples'] = []
        if example not in statPack[cat1][cat2]['examples']:
            if len(statPack[cat1][cat2]['examples']) < 5:
                statPack[cat1][cat2]['examples'].append(example)
            else:
                randomSampleI = random.randint(2,4)
                statPack[cat1][cat2]['examples'][randomSampleI] = example
    return

#----------------------------------------
def getNextRow(inputFileReader, fileColumns):
    try: row = next(inputFileReader)
    except StopIteration:
        return None
    except Exception as e:
        return repr(e)
    if row and len(row) == len(fileColumns):
        return dict(zip(fileColumns, row))
    else:
        return ','.join(row)

#----------------------------------------
def format_UBO(rowData):

    #--data corrections / updates
    if ':' in rowData['SUBJ_DUNS']:   #--they prepended file name to first column like this: UBO_00_0819.txt:021475652
        rowData['SUBJ_DUNS'] = rowData['SUBJ_DUNS'][rowData['SUBJ_DUNS'].find(':') + 1:]

    if rowData['BENF_TYP_CD'] == '119':
        recordType = 'PERSON'
        nameAttribute = 'NAME_FULL'
        addressPrefix = ''
    else:
        recordType = 'ORGANIZATION'
        nameAttribute = 'NAME_ORG'
        addressPrefix = 'BUSINESS_'

    #--json header
    jsonData = {}
    jsonData['DATA_SOURCE'] = 'DNB-OWNER'
    #--jsonData['RECORD_ID'] = ?? let G2 set it
    jsonData['ENTITY_TYPE'] = recordType
    jsonData['RECORD_TYPE'] = recordType
    updateStat('INPUT', recordType)

    jsonData[nameAttribute] = rowData['BENF_NME']
    updateStat(recordType, nameAttribute, rowData['BENF_NME'])

    #--affiliate them to the subject country
    if rowData['SUBJ_CTRY_CD']:
        jsonData['AFFILIATED_COUNTRY'] = rowData['SUBJ_CTRY_CD']
        updateStat(recordType, 'AFFILIATED_COUNTRY', rowData['SUBJ_CTRY_CD'])

    #--address
    addressData = {}
    addrFull = ''
    if rowData['BENF_ADR_LN1']:
        addressData[addressPrefix + 'ADDR_LINE1'] = rowData['BENF_ADR_LN1']
        addrFull += (' ' + rowData['BENF_ADR_LN1'])
    if rowData['BENF_ADR_LN2']:
        addressData[addressPrefix + 'ADDR_LINE2'] = rowData['BENF_ADR_LN2']
        addrFull += (' ' + rowData['BENF_ADR_LN2'])
    if rowData['BENF_ADR_LN3']:
        addressData[addressPrefix + 'ADDR_LINE3'] = rowData['BENF_ADR_LN3']
        addrFull += (' ' + rowData['BENF_ADR_LN3'])
    if rowData['BENF_PRIM_TOWN']:
        addressData[addressPrefix + 'ADDR_CITY'] = rowData['BENF_PRIM_TOWN']
        addrFull += (' ' + rowData['BENF_PRIM_TOWN'])
    if rowData['BENF_CNTY'] or rowData['BENF_PROV_OR_ST']:
        addressData[addressPrefix + 'ADDR_STATE'] = (rowData['BENF_CNTY'] + ' ' + rowData['BENF_PROV_OR_ST']).strip()
        addrFull += (' ' + (rowData['BENF_CNTY'] + ' ' + rowData['BENF_PROV_OR_ST']).strip())
    if rowData['BENF_POST_CD']:
        addressData[addressPrefix + 'ADDR_POSTAL_CODE'] = rowData['BENF_POST_CD']
        addrFull += (' ' + rowData['BENF_POST_CD'])
    if rowData['BENF_CTRY_CD']:
        addressData[addressPrefix + 'COUNTRY'] = rowData['BENF_CTRY_CD']
        addrFull += (' ' + rowData['BENF_CTRY_CD'])
    if addressData:
        jsonData.update(addressData)
        updateStat(recordType, 'ADDRESS', addrFull.strip())

    #--these are good identifiers
    if rowData['BENF_DUNS']:
        jsonData['DUNS_NUMBER'] = rowData['BENF_DUNS']
        updateStat(recordType, 'DUNS_NUMBER')
    if rowData['BENF_ID']:
        jsonData['DNB_OWNER_ID'] = rowData['BENF_ID']
        updateStat(recordType, 'DNB_OWNER_ID')

    #--these aren't currently populated but maybe one day!
    if rowData['NATY']:
        jsonData['NATIONALITY'] = rowData['NATY']
        updateStat(recordType, 'NATIONALITY', rowData['NATY'])
    if rowData['DT_OF_BRTH']:
        jsonData['DATE_OF_BIRTH'] = rowData['DT_OF_BRTH']
        updateStat(recordType, 'DATE_OF_BIRTH', rowData['DT_OF_BRTH'])

    #--relate them to the company they own and use their group association for matching
    if rowData['SUBJ_DUNS']:
        #jsonData['RELATIONSHIP_TYPE'] = 'OWNER_OF'
        #jsonData['RELATIONSHIP_KEY'] = rowData['SUBJ_DUNS']
        #updateStat(recordType, 'RELATIONSHIP')
        jsonData['GROUP_ASSN_ID_TYPE'] = 'DUNS'
        jsonData['GROUP_ASSN_ID_NUMBER'] = rowData['SUBJ_DUNS']
        updateStat(recordType, 'GROUP_ASSN_ID', rowData['SUBJ_DUNS'])
    if rowData['SUBJ_NME']:
        jsonData['GROUP_ASSOCIATION_ORG_NAME'] = rowData['SUBJ_NME']
        updateStat(recordType, 'GROUP_ASSOCIATION_NAME', rowData['SUBJ_NME'])

    #--additional useful information
    if rowData['BENF_LGL_FORM_DESC']:
        jsonData['LEGAL_FORM'] = rowData['BENF_LGL_FORM_DESC']
        updateStat(recordType, 'LEGAL_FORM', rowData['BENF_LGL_FORM_DESC'])
    if rowData['DIRC_OWRP_PCTG']: 
        jsonData['DIRECT_OWNERSHIP_PERCENT'] = float(rowData['DIRC_OWRP_PCTG'])
        updateStat(recordType, 'DIRECT_OWNERSHIP_PERCENT', rowData['DIRC_OWRP_PCTG'])

    return [jsonData]  #--must return a list even though only 1

#----------------------------------------
def format_GCA(rowData):

    #--data corrections / updates
    recordType = 'PERSON'

    #--json header
    jsonData = {}
    jsonData['DATA_SOURCE'] = 'DNB-CONTACT'
    jsonData['RECORD_ID'] = rowData['CONTACT_ID']
    jsonData['ENTITY_TYPE'] = recordType
    jsonData['RECORD_TYPE'] = recordType

    #--map the name
    fullName = ''
    if rowData['NAMEPREFIX']:
        jsonData['PRIMARY_NAME_PREFIX'] = rowData['NAMEPREFIX']
        fullName += (' ' + rowData['NAMEPREFIX'])
    if rowData['FIRSTNAME']:
        jsonData['PRIMARY_NAME_FIRST'] = rowData['FIRSTNAME']
        fullName += (' ' + rowData['FIRSTNAME'])
    if rowData['MIDDLENAME']:
        jsonData['PRIMARY_NAME_MIDDLE'] = rowData['MIDDLENAME']
        fullName += (' ' + rowData['MIDDLENAME'])
    if rowData['LASTNAME']:
        jsonData['PRIMARY_NAME_LAST'] = rowData['LASTNAME']
        fullName += (' ' + rowData['LASTNAME'])
    if rowData['NAMESUFFIX']:
        jsonData['PRIMARY_NAME_SUFFIX'] = rowData['NAMESUFFIX']
        fullName += (' ' + rowData['NAMESUFFIX'])
    fullName = fullName.strip()
    if fullName:
        updateStat(recordType, 'NAME-PRIMARY', fullName)

    #--add an aka name
    if rowData['GCA_NICKNAME'] and rowData['LASTNAME']:
        jsonData['AKA_NAME_FIRST'] = rowData['GCA_NICKNAME']
        jsonData['AKA_NAME_LAST'] = rowData['LASTNAME']
        updateStat(recordType, 'NAME-AKA', fullName)

    #--gender
    if rowData['GCA_GENDER']:
        jsonData['GENDER'] = rowData['GCA_GENDER']
        updateStat(recordType, 'GENDER', rowData['GCA_GENDER'])

    #--map the address
    fullAddress = ''
    if rowData['GCA_STREETADDRESS1']:
        jsonData['PRIMARY_ADDR_LINE1'] = rowData['GCA_STREETADDRESS1']
        fullAddress += (' ' + rowData['GCA_STREETADDRESS1'])
    if rowData['GCA_STREETADDRESS2']:
        jsonData['PRIMARY_ADDR_LINE2'] = rowData['GCA_STREETADDRESS2']
        fullAddress += (' ' + rowData['GCA_STREETADDRESS2'])
    if rowData['GCA_CITYNAME']:
        jsonData['PRIMARY_ADDR_CITY'] = rowData['GCA_CITYNAME']
        fullAddress += (' ' + rowData['GCA_CITYNAME'])
    if rowData['GCA_STATEPROVINCECODE']:
        jsonData['PRIMARY_ADDR_STATE'] = rowData['GCA_STATEPROVINCECODE']
        fullAddress += (' ' + rowData['GCA_STATEPROVINCECODE'])
    if rowData['GCA_POSTALCODE']:
        jsonData['PRIMARY_POSTAL_CODE'] = rowData['GCA_POSTALCODE']
        fullAddress += (' ' + rowData['GCA_POSTALCODE'])
    if rowData['GCA_COUNTRYCODE']:
        jsonData['PRIMARY_COUNTRY'] = rowData['GCA_COUNTRYCODE']
        fullAddress += (' ' + rowData['GCA_COUNTRYCODE'])
    fullAddress = fullAddress.strip()
    if fullAddress:
        updateStat(recordType, 'ADDRESS-PRIMARY', fullAddress)

    #--phones and email
    if rowData['PRIMARYPHONE']:
        jsonData['PRIMARY_PHONE_NUMBER'] = rowData['PRIMARYPHONE']
        updateStat(recordType, 'PHONE-PRIMARY', rowData['PRIMARYPHONE'])
        if rowData['PRIMARYPHONEEXTENSION']:
            jsonData['PRIMARY_PHONE_EXT'] = rowData['PRIMARYPHONEEXTENSION']
    if rowData['SECONDARYPHONE']:
        jsonData['SECONDARY_PHONE_NUMBER'] = rowData['SECONDARYPHONE']
        updateStat(recordType, 'PHONE-SECONDARY', rowData['SECONDARYPHONE'])
        if rowData['SECONDARYPHONEEXTENSION']:
            jsonData['SECONDARY_PHONE_EXT'] = rowData['SECONDARYPHONEEXTENSION']
    if rowData['EMAIL']:
        jsonData['EMAIL_ADDRESS'] = rowData['EMAIL']
        updateStat(recordType, 'EMAIL_ADDRESS', rowData['EMAIL'])

    #--relate them to the company they own and use their group association for matching
    if rowData['DUNS_ID']:
        #jsonData['RELATIONSHIP_TYPE'] = 'CONTACT'
        #jsonData['RELATIONSHIP_KEY'] = rowData['DUNS_ID']
        #updateStat(recordType, 'RELATIONSHIP')
        jsonData['GROUP_ASSN_ID_TYPE'] = 'DUNS'
        jsonData['GROUP_ASSN_ID_NUMBER'] = rowData['DUNS_ID']
        updateStat(recordType, 'GROUP_ASSN_ID', rowData['DUNS_ID'])
    if rowData['GCA_BUSINESSNAME']:
        jsonData['GROUP_ASSOCIATION_ORG_NAME'] = rowData['GCA_BUSINESSNAME']
        updateStat(recordType, 'GROUP_ASSOCIATION_NAME', rowData['GCA_BUSINESSNAME'])

    #--other info
    if rowData['JOBTITLE']:
        jsonData['JOB_TITLE'] = rowData['JOBTITLE']
        updateStat(recordType, 'JOB_TITLE', rowData['JOBTITLE'])

    return [jsonData]  #--must return a list even though only 1

#----------------------------------------
def mapJsonAddr(addrData, usageType):
    jsonAddr = {}
    addrType = usageType + '_'
    fullAddress = ''
    if 'streetAddress' in addrData and 'line1' in addrData['streetAddress'] and addrData['streetAddress']['line1']:
        jsonAddr[addrType + 'ADDR_LINE1'] = addrData['streetAddress']['line1']
        fullAddress += (' ' + addrData['streetAddress']['line1'])
    if 'streetAddress' in addrData and 'line2' in addrData['streetAddress'] and addrData['streetAddress']['line2']:
        jsonAddr[addrType + 'ADDR_LINE2'] = addrData['streetAddress']['line2']
        fullAddress += (' ' + addrData['streetAddress']['line2'])
    if 'addressLocality' in addrData and 'name' in addrData['addressLocality'] and addrData['addressLocality']['name']:
        jsonAddr[addrType + 'ADDR_CITY'] = addrData['addressLocality']['name']
        fullAddress += (' ' + addrData['addressLocality']['name'])
    if 'addressRegion' in addrData and 'abbreviatedName' in addrData['addressRegion'] and addrData['addressRegion']['abbreviatedName']:
        jsonAddr[addrType + 'ADDR_STATE'] = addrData['addressRegion']['abbreviatedName']
        fullAddress += (' ' + addrData['addressRegion']['abbreviatedName'])
    elif 'addressRegion' in addrData and 'name' in addrData['addressRegion'] and addrData['addressRegion']['name']:
        jsonAddr[addrType + 'ADDR_STATE'] = addrData['addressRegion']['name']
        fullAddress += (' ' + addrData['addressRegion']['name'])
    if 'postalCode' in addrData and addrData['postalCode']:
        jsonAddr[addrType + 'ADDR_POSTAL_CODE'] = addrData['postalCode']
        fullAddress += (' ' + addrData['postalCode'])
    if 'addressCountry' in addrData and 'isoAlpha2Code' in addrData['addressCountry'] and addrData['addressCountry']['isoAlpha2Code']:
        jsonAddr[addrType + 'ADDR_COUNTRY'] = addrData['addressCountry']['isoAlpha2Code']
        fullAddress += (' ' + addrData['addressCountry']['isoAlpha2Code'])
    elif 'addressCountry' in addrData and 'name' in addrData['addressCountry'] and addrData['addressCountry']['name']:
        jsonAddr[addrType + 'ADDR_COUNTRY'] = addrData['addressCountry']['name']
        fullAddress += (' ' + addrData['addressCountry']['name'])
    return fullAddress, jsonAddr

#----------------------------------------
def format_CMPCVF(rowData):

    jsonList = []

    #--data corrections / updates
    rowData = rowData['organization']
    recordType = 'ORGANIZATION'

    #--json header
    jsonData = {}
    jsonData['DATA_SOURCE'] = 'DNB-COMPANY'
    jsonData['RECORD_ID'] = rowData['duns']
    jsonData['ENTITY_TYPE'] = recordType
    jsonData['RECORD_TYPE'] = recordType

    jsonData['DUNS_NUMBER'] = rowData['duns']
    updateStat(recordType, 'DUNS_NUMBER', rowData['duns'])

    #--map the name
    thisDuns = rowData['duns']
    bestName = ''
    if 'primaryName' in rowData and rowData['primaryName']:
        bestName = rowData['primaryName']
        jsonData['PRIMARY_NAME_ORG'] = rowData['primaryName']
        updateStat(recordType, 'NAME_ORG_PRIMARY', rowData['primaryName'])
    #"registeredName": null,

    #--map the address
    if 'primaryAddress' in rowData and rowData['primaryAddress']:
        addrType = 'PRIMARY'
        fullAddress, jsonAddr = mapJsonAddr(rowData['primaryAddress'], addrType)
        if fullAddress:
            jsonData.update(jsonAddr)
            updateStat(recordType, addrType + 'ADDRESS', fullAddress)



    #--other things to consider adding ...
    #--"minorTownName": null,
    #--"postOfficeBox": {},
    #--"latitude": 26.662361,
    #--"longitude": -80.112527,
    #--"geographicalPrecision": {
    #--"description": "Street Address Centroid",
    #--"dnbCode": 30257
    #--},
    #--"isRegisteredAddress": false,
    #--"locationOwnership": {},
    #--"congressionalDistricts": [],
    #--"isResidentialAddress": null
    #--},
    #--"registeredAddress": {},
    #--"mailingAddress": {},
    #--"formerRegisteredAddresses": [],
    #--"registrationNumbers": [],
    #--"telephone": [
    #--  {
    #--    "telephoneNumber": "5614333976",
    #--    "isdCode": "1",
    #--    "isUnreachable": false
    #--  }
    #--],
    #--"websiteAddress": [],
    #--"email": []
    #--"industryCodes": [
    #--  {
    #--    "code": "722513",
    #--    "description": "Limited-Service Restaurants",
    #--    "typeDescription": "North American Industry Classification System 2017",
    #--    "typeDnBCode": 30832,
    #--    "priority": 1
    #--  },
    #--"incorporatedDate": null,
    #--"startDate": "2004",
    #--"primaryName": "Carribbean Spotlight",
    #--"controlOwnershipDate": "2004",
    #--"businessEntityType": {},
    #--"legalForm": {},
    #--"controlOwnershipType": {},
    #--"franchiseOperationType": {},

    #--link to parents (disabled for now)
    if False: #--'corporateLinkage' in rowData and rowData['corporateLinkage']:
        print('thisDuns', thisDuns, bestName)
        found = False
        if 'globalUltimate' in rowData['corporateLinkage'] and 'duns' in rowData['corporateLinkage']['globalUltimate']:
            found = True
            globalDuns = rowData['corporateLinkage']['globalUltimate']['duns']
            globalName = rowData['corporateLinkage']['globalUltimate']['primaryName'] if 'primaryName' in rowData['corporateLinkage']['globalUltimate'] else 'n/a'
            print('globalDuns', globalDuns, globalName) 
        if 'domesticUltimate' in rowData['corporateLinkage'] and 'duns' in rowData['corporateLinkage']['domesticUltimate']:
            found = True
            domesticDuns = rowData['corporateLinkage']['domesticUltimate']['duns']
            domesticName = rowData['corporateLinkage']['domesticUltimate']['primaryName'] if 'primaryName' in rowData['corporateLinkage']['domesticUltimate'] else 'n/a'
            print('domesticDuns', domesticDuns, domesticName) 
        if 'parent' in rowData['corporateLinkage'] and 'duns' in rowData['corporateLinkage']['parent']:
            found = True
            parentDuns = rowData['corporateLinkage']['parent']['duns']
            parentName = rowData['corporateLinkage']['parent']['primaryName'] if 'primaryName' in rowData['corporateLinkage']['parent'] else 'n/a'
            print('parentDuns', parentDuns, parentName) 
        if 'headquarter' in rowData['corporateLinkage'] and 'duns' in rowData['corporateLinkage']['headquarter']:
            found = True
            headquarterDuns = rowData['corporateLinkage']['headquarter']['duns']
            headquarterName = rowData['corporateLinkage']['headquarter']['primaryName'] if 'primaryName' in rowData['corporateLinkage']['headquarter'] else 'n/a'
            print('headquarterDuns', headquarterDuns, headquarterName) 

        if not found:
            print(rowData['corporateLinkage'])
        pause('-----')

    #--current and most senior executives
    principleList = []
    if 'mostSeniorPrincipals' in rowData and rowData['mostSeniorPrincipals']:
        principleList += rowData['mostSeniorPrincipals']
    if 'currentPrincipals' in rowData and rowData['currentPrincipals']:
        principleList += rowData['currentPrincipals']
    for rowData1 in principleList:
        recordType1 = 'PERSON' if rowData1['subjectType'] == 'Individual' else 'GENERIC'
        updateStat(recordType1, rowData1['subjectType'])

        jsonData1 = {}
        jsonData1['DATA_SOURCE'] = 'DNB-PRINCIPLE'
        #--jsonData1['RECORD_ID'] = #--there is no key, let G2 hash it)
        jsonData1['ENTITY_TYPE'] = recordType1
        jsonData1['RECORD_TYPE'] = recordType1

        fullName = ''
        if 'namePrefix' in rowData1 and rowData1['namePrefix']:
            fullName += (' ' + rowData1['namePrefix'])
            jsonData1['PRIMARY_NAME_PREFIX'] = rowData1['namePrefix']
        if 'givenName' in rowData1 and rowData1['givenName']:
            fullName += (' ' + rowData1['givenName'])
            jsonData1['PRIMARY_NAME_FIRST'] = rowData1['givenName']
        if 'middleName' in rowData1 and rowData1['middleName']:
            fullName += (' ' + rowData1['middleName'])
            jsonData1['PRIMARY_NAME_MIDDLE'] = rowData1['middleName']
        if 'familyName' in rowData1 and rowData1['familyName']:
            fullName += (' ' + rowData1['familyName'])
            jsonData1['PRIMARY_NAME_LAST'] = rowData1['familyName']
        if 'nameSuffix' in rowData1 and rowData1['nameSuffix']:
            fullName += (' ' + rowData1['nameSuffix'])
            jsonData1['PRIMARY_NAME_SUFFIX'] = rowData1['nameSuffix']
        if fullName:
            updateStat(recordType1, 'PARSED_NAME', fullName.strip())

        #--map the address
        if 'primaryAddress' in rowData1 and rowData1['primaryAddress']:
            print(thisDuns)
            addrType = 'PRIMARY'
            fullAddress, jsonAddr = mapJsonAddr(rowData1['primaryAddress'], addrType)
            if fullAddress:
                jsonData1.update(jsonAddr)
                updateStat(recordType, addrType + 'ADDRESS', fullAddress)
        
        if 'birthDate' in rowData1 and rowData1['birthDate']:
            jsonData1['DATE_OF_BIRTH'] = rowData1['birthDate']
            updateStat(recordType1, 'DOB', rowData1['birthDate'])
        if 'gender' in rowData1 and 'description' in rowData1['gender'] and rowData1['gender']['description']:
            jsonData1['GENDER'] = rowData1['gender']['description']
            updateStat(recordType1, 'GENDER', rowData1['gender']['description'])
        if 'nationality' in rowData1 and 'isoAlpha2Code' in rowData1['nationality'] and rowData1['nationality']['isoAlpha2Code']:
            jsonData1['NATIONALITY'] = rowData1['nationality']['isoAlpha2Code']
            updateStat(recordType1, 'NATIONALITY', rowData1['nationality']['isoAlpha2Code'])

        if 'jobTitles' in rowData1 and rowData1['jobTitles']:
            jobTitleList = []
            for titleData in rowData1['jobTitles']:
                jobTitleList.append(titleData['title'])
            jsonData1['JOB_TITLE'] = ','.join(jobTitleList) 

        #--relate them to the company and use their group association for matching
        #jsonData['RELATIONSHIP_TYPE'] = 'CONTACT'
        #jsonData['RELATIONSHIP_KEY'] = rowData['DUNS_ID']
        #updateStat(recordType, 'RELATIONSHIP')
        jsonData1['GROUP_ASSN_ID_TYPE'] = 'DUNS'
        jsonData1['GROUP_ASSN_ID_NUMBER'] = thisDuns
        updateStat(recordType1, 'GROUP_ASSN_ID', thisDuns)
        if bestName:
            jsonData1['GROUP_ASSOCIATION_ORG_NAME'] = bestName
            updateStat(recordType1, 'GROUP_ASSOCIATION_NAME', bestName)

        #--current and most senior principles overlap
        if jsonData1 not in jsonList:
            jsonList.append(jsonData1)

    jsonList.append(jsonData)


    return jsonList

#----------------------------------------
def processFile(inputFileName):
    updateStat('INPUT', 'FILE_COUNT')
    global shutDown, outputFileHandle, outputFileName

    try:
        if 'encoding' in dnbFormat: 
            inputFileHandle = open(inputFileName, 'r', encoding=dnbFormat['encoding'])
        else:
            inputFileHandle = open(inputFileName, 'r')
    except IOError as err:
        print('')
        print(err)
        print('')
        return 1

    #--set up a reader
    if dnbFormat['fileType'].upper() == 'JSON':
        inputFileReader = inputFileHandle
    else:

        if dnbFormat['fileType'].upper() == 'TAB':
            delimiter = '\t'
        elif dnbFormat['fileType'].upper() == 'PIPE':
            delimiter = '|'
        elif dnbFormat['fileType'].upper() == 'CSV':
            delimiter = ','
        else:
            delimiter = dnbFormat['delimiter'] if 'delimiter' in dnbFormat else None
        if not delimiter:
            print('')
            print('File type %s not supported')
            print('')
            return 1
        quotechar = dnbFormat['quotechar'] if 'quotechar' in dnbFormat else None

        try:
            if quotechar: 
                inputFileReader = csv.reader(inputFileHandle, delimiter=delimiter, quotechar=quotechar)
            else:
                inputFileReader = csv.reader(inputFileHandle, delimiter=delimiter)
        except csv.Error as err:
            print('')
            print(err)
            print('')
            return 1

        #if 'headerRows' in dnbFormat:
        #    for i in range(int(dnbFormat['headerRows']) if dnbFormat['headerRows'].isdigit() else 1):
        #        headerRow = next(inputFileReader)
        #        if len(headerRow) != len(fileColumns):
        #            print('')
        #            print('File mismatch: expected %s columns, got %s' % (len(dnbFormat['columns']), len(headerRow)))
        #            print('')
        #            return 1

    #--open an output file if output is a directory
    if not outputIsFile:
        outputFileName = outputFilePath + os.path.basename(inputFileName) + '.json'
        try: outputFileHandle = open(outputFileName, "w", encoding='utf-8')
        except IOError as err:
            print('')
            print('Could not open output file %s for writing' % outputFileName)
            print(' %s' % err)
            print('')
            sys.exit(1)

    badCnt = 0
    rowCnt = 0
    for row in inputFileReader:
        updateStat('INPUT', 'ROW_COUNT')
        rowCnt += 1
        rowData = None

        #--validate json
        if dnbFormat['fileType'].upper() == 'JSON':
            try: rowData = json.loads(row)
            except: 
                print('Invalid json in row %s' % rowCnt)

        #--validate csv
        elif len(row) != len(dnbFormat['columns']):
            print('Column mismatch in row %s: expected %s columns, got %s ... "%s"' % (rowCnt, len(dnbFormat['columns']), len(row), delimiter.join(row)[0:50]))
        elif dnbFormat['columns'][0].upper() + '|' + dnbFormat['columns'][1].upper() == (str(row[0]).upper() if row[0] else '') + '|' + (str(row[1]).upper() if row[1] else ''):
            print('Column header detected in row %s' % rowCnt)
            continue
        else:
            rowData = dict(zip(dnbFormat['columns'], row))

        #--bad row processing
        if not rowData:
            badCnt += 1
            if badCnt == 10 and rowCnt == 10:
                print('')
                print('Shutting down, too many errors')
                print('')
                shutDown = True #--bad csv header
                break
            else:
                continue

        #--perform the mapping
        if dnbFormat['formatCode'] == 'UBO':
            jsonList = format_UBO(rowData)
        elif dnbFormat['formatCode'] == 'GCA':
            jsonList = format_GCA(rowData)
        elif dnbFormat['formatCode'] == 'CMPCVF':
            jsonList = format_CMPCVF(rowData)
        else:
            print('')
            print('No conversions for format code %s' % dnbFormat['formatCode'])
            print('')
            shutDown = True
            break

        #--process each json record returned
        for jsonData in jsonList:

            #--add watch_list keys
            jsonData = baseLibrary.jsonUpdater(jsonData)

            #--write it to file
            msg = json.dumps(jsonData)
            try: outputFileHandle.write(msg + '\n')
            except IOError as err:
                print('')
                print('Could not write to %s' % outputFileName)
                print(' %s' % err)
                print('')
                shutDown = True
                break

        if rowCnt % progressInterval == 0:
            print('%s records processed' % rowCnt)

        if shutDown:
            break

    if not shutDown:
        print('%s records processed, complete!' % rowCnt)
    
    #--close all inputs and outputs
    #--open an output file if output is a directory
    if not outputIsFile:
        outputFileHandle.close()
    inputFileHandle.close()
    #for i in range(len(mappingDoc['outputs'])):
    #    print('%s rows written to %s, %s rows skipped' % (mappingDoc['outputs'][i]['rowsWritten'], mappingDoc['outputs'][i]['fileName'], mappingDoc['outputs'][i]['rowsSkipped']))
    #for fileName in openFiles:
    #    openFiles[fileName].close()

    return shutDown

#----------------------------------------
if __name__ == "__main__":
    appPath = os.path.dirname(os.path.abspath(sys.argv[0]))

    global shutDown
    shutDown = False
    signal.signal(signal.SIGINT, signal_handler)
    procStartTime = time.time()
    progressInterval = 10000

    #--load the dnb file formats
    dnbFormatFile = appPath + os.path.sep + 'dnb_formats.json'
    print(dnbFormatFile)
    if not os.path.exists(dnbFormatFile):
        print('')
        print('Format file missing: %s' % dnbFormatFile)
        print('')
        sys.exit(1)
    try: dnbFormats = json.load(open(dnbFormatFile,'r'))
    except json.decoder.JSONDecodeError as err:
        print('')
        print('JSON error %s in %s' % (err, dnbFormatFile))
        print('')
        sys.exit(1)

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-f', '--dnb_format', default=os.getenv('dnb_format'.upper(), None), type=str, help='choose CMPCVF, UBO, or GCA')
    argparser.add_argument('-i', '--input_spec', default=os.getenv('input_spec'.upper(), None), type=str, help='the name of one or more DNB files to map (place in quotes if you use wild cards)')
    argparser.add_argument('-o', '--output_path', default=os.getenv('output_path'.upper(), None), type=str, help='output directory or file name for mapped json records')
    argparser.add_argument('-l', '--log_file', default=os.getenv('log_file', None), type=str, help='optional statistics filename (json format).')
    args = argparser.parse_args()
    dnbFormatCode = args.dnb_format
    inputFileSpec = args.input_spec
    outputFilePath = args.output_path
    logFile = args.log_file
    
    #--verify dnb format code
    if not dnbFormatCode:
        print('')
        print('Please select a DNB format code from dnb_formats.json')
        print('')
        sys.exit(1)
    dnbFormat = None
    for formatData in dnbFormats:
        if formatData['formatCode'].upper() == dnbFormatCode.upper():
            dnbFormat = formatData
    if not dnbFormat:
        print('')
        print('DNB format code %s not found in dnb_formats.json' % dnbFormatCode)
        print('')
        sys.exit(1)

    #--verify input files to process
    if not inputFileSpec:
        print('')
        print('Please select a set of %s files to process' % dnbFormatCode)
        print('')
        sys.exit(1)
    inputFileList = glob.glob(inputFileSpec)
    if len(inputFileList) == 0:
        print('')
        print('No files found matching %s' % inputFileSpec)
        print('')
        sys.exit(1)

    #--open output if a single file was specified
    if not outputFilePath:
        print('')
        print('Please select a directory or file to write the output files to')
        print('')
        sys.exit(1)
    outputIsFile = not os.path.isdir(outputFilePath)
    if outputIsFile:
        try: outputFileHandle = open(outputFilePath, "w", encoding='utf-8')
        except IOError as err:
            print('')
            print('Could not open output file %s for writing' % outputFilePath)
            print(' %s' % err)
            print('')
            sys.exit(1)
    else:
        if outputFilePath[-1] != os.path.sep:
            outputFilePath += os.path.sep

    #--initialize some stats
    statPack = {}
    
    #--for each input file
    inputFileNum = 0
    for inputFileName in sorted(inputFileList):
        inputFileNum += 1
        fileDisplay = 'Processing file %s of %s - %s ...' % (inputFileNum, len(inputFileList), inputFileName)
        print('')
        print('-' * len(fileDisplay))
        print(fileDisplay)
    
        shutDown = processFile(inputFileName)
        if shutDown:
            break

    print('')
    print('%s of %s files processed' % (inputFileNum, len(inputFileList)))

    if outputIsFile:
        outputFileHandle.close()

    #--write statistics file
    if logFile: 
        print('')
        statPack['BASE_LIBRARY'] = baseLibrary.statPack
        with open(logFile, 'w') as outfile:
            json.dump(statPack, outfile, indent=4, sort_keys = True)    
        print('Mapping stats written to %s' % logFile)
    
    print('')
    elapsedMins = round((time.time() - procStartTime) / 60, 1)
    if shutDown == 0:
        print('Process completed successfully in %s minutes!' % elapsedMins)
    else:
        print('Process aborted after %s minutes!' % elapsedMins)
    print('')
    
    sys.exit(0)

    sys.exit(0)
