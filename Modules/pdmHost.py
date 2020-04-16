

from Modules.logging import loggingPDM
from Modules.output import sendZigateCmd

import Domoticz
import datetime
import os.path
import json

PDM_RECORD_ID = {
    0x10:   'PDM_ID_APP_VERSION',
    0x01:   'PDM_ID_APP_ZLL_CMSSION',
    0xF000: 'PDM_ID_INTERNAL_AIB',
    0xF001: 'PDM_ID_INTERNAL_BINDS',
    0xF002: 'PDM_ID_INTERNAL_GROUPS',
    0xF003: 'PDM_ID_INTERNAL_APS_KEYS', 
    0xF004: 'PDM_ID_INTERNAL_TC_TABLE',
    0xF005: 'PDM_ID_INTERNAL_TC_LOCATIONS',
    0xF100: 'PDM_ID_INTERNAL_NIB_PERSIST',
    0xF101: 'PDM_ID_INTERNAL_CHILD_TABLE',
    0xF102: 'PDM_ID_INTERNAL_SHORT_ADDRESS_MAP',
    0xF103: 'PDM_ID_INTERNAL_NWK_ADDRESS_MAP',
    0xF104: 'PDM_ID_INTERNAL_ADDRESS_MAP_TABLE',
    0xF105: 'PDM_ID_INTERNAL_SEC_MATERIAL_KEY'}

PDM_E_STATUS_OK = '00'
PDM_E_STATUS_INVLD_PARAM = '01'
#  EEPROM based PDM codes
PDM_E_STATUS_PDM_FULL = '02'
PDM_E_STATUS_NOT_SAVED = '03'
PDM_E_STATUS_RECOVERED = '04'
PDM_E_STATUS_PDM_RECOVERED_NOT_SAVED = '05'
PDM_E_STATUS_USER_BUFFER_SIZE = '06'
PDM_E_STATUS_BITMAP_SATURATED_NO_INCREMENT = '07'
PDM_E_STATUS_BITMAP_SATURATED_OK = '08'
PDM_E_STATUS_IMAGE_BITMAP_COMPLETE = '09'
PDM_E_STATUS_IMAGE_BITMAP_INCOMPLETE = '0A'
PDM_E_STATUS_INTERNAL_ERROR = '0B'

MAX_LOAD_BLOCK_SIZE = 192   # Max Block size in Bytes, send to Zigate

def openPDM( self ):

    """
    Open PDM file and load into the plugin Datastructure
    The file is closed after loading
    """

    zigatePDMfilename = self.pluginconf.pluginConf['pluginData'] + "zigatePDM-%02d.json" %self.HardwareID
    if os.path.isfile(zigatePDMfilename):
        with open( zigatePDMfilename, 'r') as zigatePDMfile:
            self.PDM = {}
            try:
                self.PDM = json.load( zigatePDMfile, encoding=dict)

            except json.decoder.JSONDecodeError as e:
                Domoticz.Error("error while reading Zigate PDM on Host %s, not JSON: %s" %( zigatePDMfilename,e))
    #loggingPDM( self, 'Debug2', "Load " + zigatePDMfilename + " = " + str(self.PDM))
    return

def savePDM( self):
    """
    Save the Data Structutre to file
    """

    zigatePDMfilename = self.pluginconf.pluginConf['pluginData'] + "zigatePDM-%02d.json" %self.HardwareID
    #loggingPDM( self, 'Debug2', "Write " + zigatePDMfilename + " = " + str(self.PDM))
    with open( zigatePDMfilename, 'wt') as zigatePDMfile:
        try:
            json.dump( self.PDM, zigatePDMfile, indent=4, sort_keys=True)
            #json.dump( self.PDM, zigatePDMfile)
        except IOError:
            Domoticz.Error("Error while writing Zigate Network Details%s" %zigatePDMfile)
    return


def pdmHostAvailableRequest(self, MsgData ):
    #Decode0300

    self.PDMready = False
    loggingPDM( self, 'Debug2',  "pdmHostAvailableRequest - receiving 0x0300 with data: %s" %(MsgData))

    status = PDM_E_STATUS_OK
    loggingPDM( self, 'Debug2',  "pdmHostAvailableRequest - Sending 0x8300 with Status: %s" %(status))

    # Allow only PDM traffic
    self.ZigateComm.PDMonly( True )

    # Open PDM file and populate the Data Structure self.PDM
    openPDM( self )
    sendZigateCmd(self, "8300", status )

    return

def pdmLoadConfirmed( self, MsgData):

    # Decode0302
    loggingPDM( self, 'Debug2',  "pdmLoadConfirmed - PDM correctly loaded in Zigate. Zigate Ready: %s" %(MsgData))
    savePDM( self )

    # Allow ALL traffic
    self.ZigateComm.PDMonly( False )

    # Let's tell the plugin that we can enter in run mode.
    self.PDMready = True

def PDMSaveRequest( self, MsgData):
    """
    We received from the zigate a buffer to write down to the PDM.
    Data can come in several blocks for the same RecordID
    #Decode0200
    """

    # Allow only PDM traffic
    self.ZigateComm.PDMonly( True )

    loggingPDM( self, 'Debug2',  "PDMSaveRequest - receiving 0x0200 with data: %s" %(MsgData))

    RecordId = MsgData[:4]                #record ID
    u16Size = MsgData[4:8]                # total PDM record size
    u16NumberOfWrites = MsgData[8:12]     # total number of block writes expected
    u16BlocksWritten = MsgData[12:16]     # This number corresponds to the block id
    dataReceived = int(MsgData[16:20],16) # Send size of this particular block (number of bytes)
    sWriteData = MsgData[20:20+(2*dataReceived)] # bytes is coded into 2 chars 


    loggingPDM( self, 'Log',  "      --------- RecordId: %s, u16Size: %s, u16BlocksWritten: %s, u16NumberOfWrites: %s, dataReceived: %s " \
            %( RecordId, u16Size, u16BlocksWritten, u16NumberOfWrites, dataReceived))


    if RecordId not in self.PDM:
        self.PDM[RecordId] = {}
        self.PDM[RecordId]['RecSize'] = u16Size
        self.PDM[RecordId]['PersistedData'] = sWriteData
    else:
        if u16Size != self.PDM[RecordId]['RecSize']:
            Domoticz.Log("PDMSaveRequest - u16Size %s received != that existing %s" %(u16Size, self.PDM[RecordId]['RecSize']))
        if int(u16BlocksWritten,16) > 0:
            # We assume the block come in the righ order
            sWriteData = self.PDM[RecordId]['PersistedData'] + sWriteData
        self.PDM[RecordId]['PersistedData'] = sWriteData

    if self.PDMready:
        savePDM(self)

    datas =  PDM_E_STATUS_OK + RecordId +  u16BlocksWritten 
    sendZigateCmd( self, "8200", datas)

    if (int(u16BlocksWritten,16) + 1) == int(u16NumberOfWrites,16):
        # Allow ALL traffic
        self.ZigateComm.PDMonly( False )
    return

def PDMLoadRequest(self, MsgData):
    """
    Retreive RecordID intothe PDM and send it back to Zigate
    Must be split into bocks as a block size is limited to 
    """
    #Decode0201
    #  Send the Host PDM to Zigate
    #

    loggingPDM( self, 'Log',  "PDMLoadRequest - receiving 0x0200 with data: %s" %(MsgData))
    RecordId = MsgData[0:4]

    # Allow only PDM traffic
    self.ZigateComm.PDMonly( True )

    if RecordId not in self.PDM:
        #Record not found
        TotalRecordSize = 0
        TotalBlocks = 0
        BlockId = 1
        CurentBlockSize = 0

        datas = PDM_E_STATUS_OK                 # response status
        datas += RecordId                       # record id
        datas += '%04x' %TotalRecordSize        # total record size in bytes
        datas += '%04x' %TotalBlocks            # total number of expected blocks for this record
        datas += '%04x' %BlockId                # block number for this record
        datas += '%04x' %CurentBlockSize        # size of this block in bytes

        loggingPDM( self, 'Log', "PDMLoadRequest - Sending 0x8201 : RecordId: %s TotalRecordSize: %s TotalBlocks: %s BlockId: %s CurentBlockSize: %s" \
                %(RecordId, TotalRecordSize, TotalBlocks, BlockId, CurentBlockSize))

        sendZigateCmd( self, "8201", datas)
        # Allow ALL traffic
        self.ZigateComm.PDMonly( False )
    else:
        # Let's retreive the recordID Data and RecordSize from PDM
        persistedData = self.PDM[RecordId]['PersistedData']
        u16TotalRecordSize = int(self.PDM[RecordId]['RecSize'],16)

        # Sanity Check is the retreived Data lenght match the expected record size
        if len(persistedData) != 2 * u16TotalRecordSize:
            Domoticz.Error("PDMLoadRequest - Loaded data is incomplete, Real size: %s Expected size: %s" %(len(persistedData), u16TotalRecordSize))
            return

        # Compute the number of Blocks. One block size is 128Bytes
        _TotalBlocks = u16TotalRecordSize // MAX_LOAD_BLOCK_SIZE
        if (u16TotalRecordSize % MAX_LOAD_BLOCK_SIZE) > 0:
            TotalBlocksToSend = _TotalBlocks + 1 
        else:
            TotalBlocksToSend = _TotalBlocks 

        # At that stage TotalBlocksToSend is the number of expected Total Blocks to be received and writen
        lowerBound = upperBound = u16CurrentBlockId = u16CurrentBlockSize = 0

        bMoreData = True
        while bMoreData:
            u16CurrentBlockSize = u16TotalRecordSize - (u16CurrentBlockId * MAX_LOAD_BLOCK_SIZE)
            if u16CurrentBlockSize > MAX_LOAD_BLOCK_SIZE:
                u16CurrentBlockSize = MAX_LOAD_BLOCK_SIZE
            else:
                bMoreData = False

            u16CurrentBlockId += 1
            datas = '02'
            datas += RecordId
            datas += '%04x' %u16TotalRecordSize
            datas += '%04x' %TotalBlocksToSend
            datas += '%04x' %u16CurrentBlockId
            datas += '%04x' %u16CurrentBlockSize
            upperBound +=  2 * u16CurrentBlockSize
            datas += persistedData[lowerBound:upperBound]

            loggingPDM( self, 'Log', "PDMLoadRequest - Sending 0x8201 : RecordId: %s TotalRecordSize: %s TotalBlocks: %s BlockId: %s CurentBlockSize: %s" \
                %(RecordId, u16TotalRecordSize, TotalBlocksToSend, u16CurrentBlockId, u16CurrentBlockSize))
            sendZigateCmd( self, "8201", datas )

            lowerBound += 2 * u16CurrentBlockSize
            if not bMoreData:
                # Allow ALL traffic
                self.ZigateComm.PDMonly( False )
    return

def PDMDeleteAllRecord( self , MsgData):
    "E_SL_MSG_DELETE_ALL_PDM_RECORDS_REQUEST"
    "Decode0202"

    loggingPDM( self, 'Log',  "PDMDeleteAllRecord - Remove ALL records with data: %s" %(MsgData))
    del self.PDM
    self.PDM = {}
    if self.PDMready:
        savePDM(self)

    return

def PDMDeleteRecord( self, MsgData):
    "E_SL_MSG_DELETE_PDM_RECORD_REQUEST"
    "Decode0203"

    loggingPDM( self, 'Log',  "PDMDeleteRecord - receiving 0x0202 with data: %s" %(MsgData))

    RecordId = MsgData[:4]                #record ID

    if RecordId in self.PDM:
        del self.PDM[ RecordId ]
    if self.PDMready:
        savePDM(self)

    return

def PDMCreateBitmap( self, MsgData):
    #create a bitmap counter
    #Decode0204
    #https://www.nxp.com/docs/en/user-guide/JN-UG-3116.pdf
    """
    The function creates a bitmap structure for a counter in a segment of the EEPROM. 
    A user-defined ID and a start value for the bitmap counter must be specified. 
    The start value is stored in the counter’s header. A bitmap is created to store
    the incremental value of the counter (over the start value). 
    This bitmap can subsequently be incremented (by one) by calling the function PDM_eIncrementBitmap(). 
    The incremental value stored in the bitmap and the start value stored in the header
    can be read at any time using the function PDM_eGetBitmap().
    If the specified ID value has already been used or the specified start value is NULL, 
    the function returns PDM_E_STATUS_INVLD_PARAM. 
    If the EEPROM has no free segments, the function returns PDM_E_STATUS_USER_PDM_FULL.
    """

    RecordId = MsgData[0:4]
    BitMapValue = MsgData[4:12]

    loggingPDM( self, 'Log',  "PDMCreateBitmap - Create Bitmap counter RecordId: %s BitMapValue: %s" %(RecordId, BitMapValue))
    # Do what ever has to be done

    datas = RecordId
    if RecordId not in self.PDM:
        self.PDM[RecordId] = {}
    if 'Bitmap' not in self.PDM[RecordId]:
        self.PDM[RecordId]['Bitmap'] = '%08x' %0
    self.PDM[RecordId]['Bitmap'] = BitMapValue

    sendZigateCmd(self, "8204", datas )

def PDMDeleteBitmapRequest( self, MsgData):
    "Delete a bitmap record"
    "Decode0205"

    RecordId = MsgData[0:4]

    loggingPDM( self, 'Log',  "PDMDeleteBitmapRequest - Delete Bitmap counter RecordId: %s" %(RecordId))
    # Do what ever has to be done
    

def PDMGetBitmapRequest( self, MsgData):
    """
    The function reads the specified counter value from the EEPROM. 
    The counter must be identified using the user-defined ID value assigned when the counter was created using 
    the function PDM_eCreateBitmap(). 
    The function returns the counter’s start value (from the counter’s header) and incremental value 
    (from the counter’s bitmap).
    The counter value is calculated as: 
        Start Value + Incremental Value
    or in terms of the function parameters:
        *pu32InitialValue + *pu32BitmapValueNote
    that the start value may be different from the one specified when the counter was created, 
    as the start value is updated each time the counter outgrows a segment and the bitmap is 
    reset to zero.
    This function should be called when the device comes up from a cold start, 
    to check whether a bitmap counter is present in EEPROM.
    If the specified ID value has already been used or a NULL pointer is provided for the received values, 
    the function returns PDM_E_STATUS_INVLD_PARAM.
    """
    #Decode0206
    loggingPDM( self, 'Log',  "PDMGetBitmapRequest - Get BitMaprequest data: %s" %(MsgData))

    RecordId = MsgData[0:4]

    status = PDM_E_STATUS_OK

    datas = status + RecordId + '%08x' %0

    if RecordId not in self.PDM:
        self.PDM[RecordId] = {}
    if 'Bitmap' not in self.PDM[RecordId]:
        self.PDM[RecordId]['Bitmap'] = '%08x' %0

    counter = int(self.PDM[RecordId]['Bitmap'],16)
    datas = status + RecordId + '%08x' %counter
    counter += 1
    datas = status + RecordId + '%08x' %counter
    sendZigateCmd(self, "8206", datas )
    loggingPDM( self, 'Debug2',  "PDMGetBitmapRequest - Sending 0x8206 data: %s" %(datas))

    return

def PDMIncBitmapRequest( self, MsgData):
    """
    The function increments the bitmap value of the specified counter in the EEPROM. 
    The counter must be identified using the user-defined ID value assigned when the counter 
    was created using the function PDM_eCreateBitmap(). 
    The bitmap can be incremented within an EEPROM segment until its value saturates (contains all 1s). 
    At this point, the function returns the code PDM_E_STATUS_SATURATED_OK. 
    The next time that this function is called, the counter is automatically moved to a 
    new segment (provided that one is available), the start value in its header is increased appropriately and 
    the bitmap is reset to zero. 
    To avoid increasing the segment Wear Count, the old segment is not formally deleted before a new segment is started. 
    If the EEPROM has no free segments when the above overflow occurs,
    the function returns the code PDM_E_STATUS_USER_PDM_FULL.
    If the specified ID value has already been used, the function returns PDM_E_STATUS_INVLD_PARAM.
    """
    #Decode0207

    loggingPDM( self, 'Log',  "PDMIncBitmapRequest - Inc BitMap request data: %s" %(MsgData))

    RecordId = MsgData[0:4]

    datas = '00' + RecordId + '%08x' %0

    if RecordId not in self.PDM:
        self.PDM[RecordId] = {}
    if 'Bitmap' not in self.PDM[RecordId]:
        self.PDM[RecordId]['Bitmap'] = '%08x' %0

    status = PDM_E_STATUS_OK
    Counter =  int(self.PDM[RecordId]['Bitmap'],16) + 1
    self.PDM[RecordId]['Bitmap'] = '%08X' %Counter

    if  int(self.PDM[RecordId]['Bitmap'],16) == 0xFFFFFFFF:
        # Let's check if counter is saturated, if so we move to a new segment (in fact on Host, simply restart at 0)
        # Next time it will be at 0
        status = PDM_E_STATUS_SATURATED_OK
        self.PDM[RecordId]['Bitmap'] = '%08X' %0

    datas = status + RecordId + '%08x' %Counter
    
    sendZigateCmd(self, "8207", datas )
    loggingPDM( self, 'Debug2',  "PDMIncBitmapRequest - Sending 0x8207 data: %s" %(datas))
    savePDM(self)

    return

def PDMExistanceRequest( self, MsgData):
    "E_SL_MSG_PDM_EXISTENCE_REQUEST"
    #Decode0208

    loggingPDM( self, 'Debug2',  "PDMExistanceRequest - receiving 0x0208 with data: %s" %(MsgData))
    RecordId = MsgData[0:4]

    recordExist = 0x00
    if RecordId in self.PDM:
        if 'PersistedData' in self.PDM[RecordId]:
            recordExist = 0x01
            persistedData = self.PDM[RecordId]['PersistedData']
            size = self.PDM[RecordId]['RecSize']
    if not recordExist:
        recordExist = 0x00
        size = '%04x' %0
        persistedData = None


    loggingPDM( self, 'Log',  "      --------- RecordId: %s, u16Size: %s, recordExist: %s" \
            %( RecordId, size, ( 0x01 == recordExist)))

    datas = RecordId
    datas += '%02x' %recordExist    # 0x00 not exist, 0x01 exist
    datas += size

    sendZigateCmd( self, "8208", datas)
    loggingPDM( self, 'Debug2',  "PDMExistanceRequest - Sending 0x8208 data: %s" %(datas))
    return
