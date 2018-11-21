# -*- coding: utf-8 -*-

import inspect
import sys
import logging
import time
from .parsers import *
from ..panel import Panel as PanelBase
from config import user as cfg

MEM_STATUS_BASE1 = 0x8000
MEM_STATUS_BASE2 = 0x1fe0

MEM_ZONE_START = 0x010
MEM_ZONE_END = MEM_ZONE_START + 0x10 * 32
MEM_OUTPUT_START = MEM_ZONE_END
MEM_OUTPUT_END = MEM_OUTPUT_START + 0x10 * 16
MEM_PARTITION_START = MEM_OUTPUT_END
MEM_PARTITION_END = MEM_PARTITION_START + 0x10 * 2
MEM_USER_START = MEM_PARTITION_END
MEM_USER_END = MEM_USER_START + 0x10 * 32
MEM_BUS_START = MEM_USER_END
MEM_BUS_END = MEM_BUS_START + 0x10 * 15
MEM_REPEATER_START = MEM_BUS_END
MEM_REPEATER_END = MEM_REPEATER_START + 0x10 * 2
MEM_KEYPAD_START = MEM_REPEATER_END
MEM_KEYPAD_END = MEM_KEYPAD_START + 0x10 * 8
MEM_SITE_START = MEM_KEYPAD_END
MEM_SITE_END = MEM_SITE_START + 0x10
MEM_SIREN_START = MEM_SITE_END
MEM_SIREN_END = MEM_SIREN_START + 0x10 * 4

logger = logging.getLogger('PAI').getChild(__name__)


class Panel(PanelBase):
    def get_message(self, name):
        try:
            return super(Panel, self).get_message(name)
        except ResourceWarning as e:
            clsmembers = dict(inspect.getmembers(sys.modules[__name__]))
            if name in clsmembers:
                return clsmembers[name]
            else:
                raise e

    def update_labels(self):
        logger.info("Updating Labels from Panel")

        output_template = dict(
            on=False,
            pulse=False)

        self.load_labels(self.core.zones, self.core.labels['zone'], MEM_ZONE_START, MEM_ZONE_END)
        logger.info("Zones: {}".format(', '.join(self.core.labels['zone'])))
        self.load_labels(self.core.outputs, self.core.labels['output'], MEM_OUTPUT_START, MEM_OUTPUT_END,
                         template=output_template)
        logger.info("Outputs: {}".format(', '.join(list(self.core.labels['output']))))
        self.load_labels(self.core.partitions, self.core.labels['partition'], MEM_PARTITION_START, MEM_PARTITION_END)
        logger.info("Partitions: {}".format(', '.join(list(self.core.labels['partition']))))
        self.load_labels(self.core.users, self.core.labels['user'], MEM_USER_START, MEM_USER_END)
        logger.info("Users: {}".format(', '.join(list(self.core.labels['user']))))
        self.load_labels(self.core.buses, self.core.labels['bus'], MEM_BUS_START, MEM_BUS_END)
        logger.info("Buses: {}".format(', '.join(list(self.core.labels['bus']))))
        self.load_labels(self.core.repeaters, self.core.labels['repeater'], MEM_REPEATER_START, MEM_REPEATER_END)
        logger.info("Repeaters: {}".format(', '.join(list(self.core.labels['repeater']))))
        self.load_labels(self.core.keypads, self.core.labels['keypad'], MEM_KEYPAD_START, MEM_KEYPAD_END)
        logger.info("Keypads: {}".format(', '.join(list(self.core.labels['keypad']))))
        self.load_labels(self.core.sites, self.core.labels['site'], MEM_SITE_START, MEM_SITE_END)
        logger.info("Sites: {}".format(', '.join(list(self.core.labels['site']))))
        self.load_labels(self.core.sirens, self.core.labels['siren'], MEM_SIREN_START, MEM_SIREN_END)
        logger.info("Sirens: {}".format(', '.join(list(self.core.labels['siren']))))

        logger.debug("Labels updated")

    def load_labels(self,
                    labelDictIndex,
                    labelDictName,
                    start,
                    end,
                    limit=range(1, 33),
                    template=dict(label='')):
        """Load labels from panel"""
        i = 1
        address = start

        if len(limit) == 0:
            return

        while address < end and i <= max(limit):
            args = dict(address=address)
            reply = self.core.send_wait(self.get_message('ReadEEPROM'), args, reply_expected=0x05)

            if reply is None:
                logger.error("Could not fully load labels")
                return

            # Avoid errors due to colision with events
            if reply.fields.value.address != address:
                continue

            payload = reply.fields.value.data
            label = payload[:16].strip(b'\0 ').replace(b'\0', b'_').replace(b' ', b'_').decode('utf-8')

            if label not in labelDictName and i in limit:
                properties = template.copy()
                properties['label'] = label
                labelDictIndex[i] = properties

                labelDictName[label] = i
            i += 1

            address += 16

    def parse_message(self, message):
        try:
            if message is None or len(message) == 0:
                return None

            if message[0] == 0x70:
                return CloseConnection.parse(message)
            elif message[0] >> 4 == 0x7:
                return ErrorMessage.parse(message)
            elif message[0] == 0x00:
                return InitializeCommunication.parse(message)
            elif message[0] == 0x10:
                return InitializeCommunicationResponse.parse(message)
            elif message[0] == 0x30:
                return SetTimeDate.parse(message)
            elif message[0] >> 4 == 0x03:
                return SetTimeDateResponse.parse(message)
            elif message[0] == 0x40:
                return PerformAction.parse(message)
            elif message[0] >> 4 == 4:
                return PerformActionResponse.parse(message)
            elif message[0] == 0x50 and message[2] == 0x80:
                return PanelStatus.parse(message)
            elif message[0] == 0x50 and message[2] < 0x80:
                return ReadEEPROM.parse(message)
            elif message[0] >> 4 == 0x05 and message[2] == 0x80:
                return PanelStatusResponse[message[3]].parse(message)
            elif message[0] >> 4 == 0x05 and message[2] < 0x80:
                return ReadEEPROMResponse.parse(message)
            #        elif message[0] == 0x60 and message[2] < 0x80:
            #            return WriteEEPROM.parse(message)
            #        elif message[0] >> 4 == 0x06 and message[2] < 0x80:
            #            return WriteEEPROMResponse.parse(message)
            elif message[0] >> 4 == 0x0e:
                return LiveEvent.parse(message)
            else:
                logger.warn("Unknown message")
        except Exception:
            logger.exception("Parsing message")

        s = 'PARSE: '
        for c in message:
            s += "{:02x} ".format(c)

        logger.debug(s)

        return None

    def initialize_communication(self, reply, PASSWORD):
        password = self.encode_password(PASSWORD)

        args = dict(product_id=reply.fields.value.product_id,
                    firmware=reply.fields.value.firmware,
                    panel_id=reply.fields.value.panel_id,
                    pc_password=password,
                    user_code=0x000000,
                    not_used1=0x19,
                    source_id=0x02
                    )

        logger.info("Initializing communication")
        reply = self.core.send_wait(self.get_message('InitializeCommunication'), args=args)

        if reply is None:
            return False

        if reply.fields.value.po.command == 0x10:
            logger.info("Authentication Success")
            return True
        elif reply.fields.value.po.command == 0x07 or reply.fields.value.po.command == 0x00:
            logger.error("Authentication Failed. Wrong Password?")
            return False

    def request_status(self, i):
        args = dict(address=MEM_STATUS_BASE1 + i)
        reply = self.core.send_wait(ReadEEPROM, args, reply_expected=0x05)

        return reply

    def process_status_bulk(self, message):
        for k in message.fields.value:
            element_type = k.split('_')[0]

            if element_type == 'pgm':
                element_type = 'output'
                limit_list = cfg.OUTPUTS
            elif element_type == 'partition':
                limit_list = cfg.PARTITIONS
            elif element_type == 'zone':
                limit_list = cfg.ZONES
            elif element_type == 'bus':
                limit_list = cfg.BUSES
            elif element_type == 'wireless-repeater':
                element_type = 'repeater'
                limit_list == cfg.REPEATERS
            elif element_type == 'wireless-keypad':
                element_type = 'keypad'
                limit_list == cfg.KEYPADS
            else:
                continue

            if k in self.core.status_cache and self.core.status_cache[k] == message.fields.value[k]:
                continue

            self.core.status_cache[k] = message.fields.value[k]

            prop_name = '_'.join(k.split('_')[1:])
            if prop_name == 'status':
                for i in message.fields.value[k]:
                    if i in limit_list:
                        self.core.update_properties(element_type, i, message.fields.value[k][i])
            else:
                for i in message.fields.value[k]:
                    if i in limit_list:
                        status = message.fields.value[k][i]
                        self.core.update_properties(element_type, i, {prop_name: status})

    def handle_status(self, message):
        """Handle MessageStatus"""

        if message.fields.value.status_request == 0:
            if time.time() - self.core.last_power_update >= cfg.POWER_UPDATE_INTERVAL:
                self.core.last_power_update = time.time()
                self.core.update_properties('system', 'power', dict(vdc=round(message.fields.value.vdc, 2)),
                                            force_publish=cfg.PUSH_POWER_UPDATE_WITHOUT_CHANGE)
                self.core.update_properties('system', 'power', dict(battery=round(message.fields.value.battery, 2)),
                                            force_publish=cfg.PUSH_POWER_UPDATE_WITHOUT_CHANGE)
                self.core.update_properties('system', 'power', dict(dc=round(message.fields.value.dc, 2)),
                                            force_publish=cfg.PUSH_POWER_UPDATE_WITHOUT_CHANGE)
                self.core.update_properties('system', 'rf',
                                            dict(rf_noise_floor=round(message.fields.value.rf_noise_floor, 2)),
                                            force_publish=cfg.PUSH_POWER_UPDATE_WITHOUT_CHANGE)

            for k in message.fields.value.troubles:
                if "not_used" in k:
                    continue

                self.core.update_properties('system', 'trouble', {k: message.fields.value.troubles[k]})

            self.process_status_bulk(message)

        elif message.fields.value.status_request >= 1 and message.fields.value.status_request <= 5:
            self.process_status_bulk(message)
