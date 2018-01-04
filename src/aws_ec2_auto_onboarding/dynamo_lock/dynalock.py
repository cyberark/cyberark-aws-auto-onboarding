import boto3
import uuid
import time
import logging


logger = logging.getLogger('dynamo_lock')


def millis_in_future(millis):
    return time.time() + (millis/1000.0)


class LockerClient:

    def __init__(self, lock_table_name, access_key=None, secret_key=None):
        self.lock_table_name = lock_table_name
        self.db = boto3.client(
            'dynamodb',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        self.locked = False
        self.guid = ""

    def _get_item_params(self, lock_name):
        return {
            'TableName': self.lock_table_name,
            'Key': {
                'name': {
                    'S': lock_name,
                }
            },
            'AttributesToGet': [
                'guid', 'expiresOn'
            ],
            'ConsistentRead': True,
        }

    def _put_item_params(self, lock_name, lock_expiry_ms, guid):
        return {
            'Item': {
                'name': {
                    'S': lock_name
                },
                'guid': {
                    'S': guid
                },
                'expiresOn': {
                    'N': str(millis_in_future(lock_expiry_ms))
                }
            },
            'TableName': self.lock_table_name
        }

    def _delete_item_params(self, lock_name):
        return {
            'Key': {
                'name': {
                    'S': lock_name,
                }
            },
            'ExpressionAttributeValues': {
                    ':ourguid': {'S': self.guid}
            },
            'TableName': self.lock_table_name,
            'ConditionExpression': "guid = :ourguid"
        }

    def acquire(self, lock_name, lock_expiry_ms):
        # First get the row for 'name'
        get_item_params = self._get_item_params(lock_name)
        # Generate a GUID for our lock
        guid = str(uuid.uuid4())
        put_item_params = self._put_item_params(lock_name, lock_expiry_ms, guid)

        try:
            data = self.db.get_item(**get_item_params)

            if 'Item' not in data:
                # Table exists, but lock not found. We'll try to add a
                # lock If by the time we try to add we find that the
                # attribute guid exists (because another client
                # grabbed it), the lock will not be added
                put_item_params['ConditionExpression'] = 'attribute_not_exists(guid)'

            # We know there's possibly a lock'. Check to see it's expired yet
            elif float(data['Item']['expiresOn']['N']) > time.time():
                return False
            else:
                # We know there's possibly a lock and it's
                # expired. We'll take over, providing that the guid of
                # the lock we read as expired is the one we're taking
                # over from. This is an atomic conditional update
                logger.warning("Expired lock found. Attempting to aquire")
                put_item_params['ExpressionAttributeValues'] = {
                    ':oldguid': {'S': data['Item']['guid']['S']}
                }
                put_item_params['ConditionExpression'] = "guid = :oldguid"
        except Exception as e:
            logger.exception(str(e))
            # Something nasty happened. Possibly table not found
            return False

        # now we're going to try to get the lock. If ANY exception
        # happens, we assume no lock
        try:
            self.db.put_item(**put_item_params)
            self.locked = True
            self.guid = guid
            return True
        except Exception:
            return False

    def release(self, lock_name):
        if not self.locked:
            return

        delete_item_params = self._delete_item_params(lock_name)

        try:
            self.db.delete_item(**delete_item_params)
            self.locked = False
            self.guid = ""
        except Exception as e:
            logger.exception(str(e))

    def spinlock(self, lock_name, lock_expiry_ms):
        while not self.acquire(lock_name, lock_expiry_ms):
            pass

    def create_lock_table(self):
        response = self.db.create_table(
            AttributeDefinitions=[
                {
                    'AttributeName': 'name',
                    'AttributeType': 'S'
                },
            ],
            TableName=self.lock_table_name,
            KeySchema=[
                {
                    'AttributeName': 'name',
                    'KeyType': 'HASH'
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )
        logger.debug(response)

    def delete_lock_table(self):
        self.db.delete_table(TableName=self.lock_table_name)


if __name__ == '__main__':
    import config

    lock = LockerClient(
        config.DYN_TABLE_NAME,
        config.DYN_ACCESS_KEY,
        config.DYN_SECRET_KEY
    )

    if lock.acquire('blah', 1000):
        print("lock acquired")
    if not lock.acquire('blah', 1000):
        print("locked")
    time.sleep(1)
    if lock.acquire('blah', 2000):
        print("re-acquired")
    lock.spinlock('blah', 1000)
    lock.release('blah')
    print("lock released")
    if lock.acquire('blah', 1000):
        print("re-acquired")
    time.sleep(1)
    if lock.acquire('blah', 1000):
        print("re-acquired after timeout")
