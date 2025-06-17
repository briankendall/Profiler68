#include <Types.h>
#include <stdlib.h>
#include <string.h>

#include "hashmap.h"

// A basic hashmap suitable for use at interrupt time. Uses a fast hash function
// and doesn't allocate any memory, instead using a block of memory provided at
// initialization time. Because we don't need to remove entries from the hash
// table, that makes it easy to allocate new entries.

typedef struct ArenaEntry {
    UInt16 keyLength;
    UInt32 value;
    UInt32 nextOffset;
    UInt8 keyData[];
} ArenaEntry;

// Jenkins one-at-a-time hash, good for 68k
static UInt32 hashKey(const UInt8 *key, UInt16 keyLength)
{
    UInt32 hash = 0;
    UInt16 i;
    
    for(i = 0; i < keyLength; ++i) {
        hash += key[i];
        hash += (hash << 10);
        hash ^= (hash >> 6);
    }
    
    hash += (hash << 3);
    hash ^= (hash >> 11);
    hash += (hash << 15);
    
    return hash;
}

static UInt32 getEntrySize(UInt16 keyLength)
{
    UInt32 result = sizeof(ArenaEntry) + keyLength;
    
    // Keep things word aligned
    if ((result & 1) == 1) {
        result++;
    }
    
    return result;
}

HashtableStatus hashtableInit(HashTable *table, void *mem, UInt32 memSize, UInt32 bucketCount)
{
    UInt32 bucketsBytes;
    
    // must be power of two
    if ((bucketCount & (bucketCount - 1)) != 0) {
        return kHashtableBadArgsError;
    }

    bucketsBytes = bucketCount * sizeof(UInt32);
    
    if (bucketsBytes >= memSize) {
        return kHashtableNotEnoughMemoryError;
    }

    table->bucketCount = bucketCount;
    table->buckets = (UInt32*)mem;
    memset(table->buckets, 0, bucketsBytes);
    
    table->arena = (UInt8*)mem + bucketsBytes;
    table->arenaSize = memSize - bucketsBytes;
    table->arenaUsed = 0;
    
    return kHashtableNoErr;
}

static Boolean hashtableLookup_(HashTable *table, const UInt8 *key, UInt16 keyLength, UInt32 hash,
                                UInt32 bucketIndex, UInt32 **outValue)
{
    UInt32 offset = table->buckets[bucketIndex];

    while(offset != 0) {
        ArenaEntry *entry = (ArenaEntry*)(table->arena + offset);

        if (entry->keyLength == keyLength && memcmp(entry->keyData, key, keyLength) == 0) {
            *outValue = &entry->value;
            return true;
        }
        
        offset = entry->nextOffset;
    }
    
    return false;
}

Boolean hashtableLookup(HashTable *table, const UInt8 *key, UInt16 keyLength, UInt32 **outValue)
{
    UInt32 hash = hashKey(key, keyLength);
    UInt32 bucketIndex = bucketIndex = hash & (table->bucketCount - 1);
    
    return hashtableLookup_(table, key, keyLength, hash, bucketIndex, outValue);
}

HashtableStatus hashtableInsertOrLookup(HashTable *table, const UInt8 *key, UInt16 keyLength, UInt32 **outValue)
{
    UInt32 hash, bucketIndex, entrySize, *bucket;
    ArenaEntry *newEntry;
    
    hash = hashKey(key, keyLength);
    bucketIndex = bucketIndex = hash & (table->bucketCount - 1);
    
    if (hashtableLookup_(table, key, keyLength, hash, bucketIndex, outValue)) {
        return kHashtableFoundKey;
    }
    
    bucket = &table->buckets[bucketIndex];

    // Not found: allocate new arena entry
    entrySize = getEntrySize(keyLength);
    
    if (table->arenaUsed + entrySize > table->arenaSize) {
        return kHashtableNotEnoughMemoryError;
    }

    newEntry = (ArenaEntry*)(table->arena + table->arenaUsed);
    newEntry->keyLength = keyLength;
    newEntry->value = 0;
    newEntry->nextOffset = *bucket; // chain to previous head
    memcpy(newEntry->keyData, key, keyLength);

    // Point bucket to new entry
    *bucket = table->arenaUsed;
    table->arenaUsed += entrySize;
    
    *outValue = &newEntry->value;

    return kHashtableInsertedKey;
}

void hashtableIterInit(HashtableIterator *it)
{
    it->arenaOffset = 0;
}

Boolean hashtableIterNext(HashTable *table, HashtableIterator *it, const UInt8 **key, UInt16 *keyLength, UInt32 **value)
{
    UInt32 entrySize;
    ArenaEntry *entry;
    
    if (it->arenaOffset >= table->arenaUsed) {
        return false;
    }
    
    entry = (ArenaEntry*)(table->arena + it->arenaOffset);
    *key = entry->keyData;
    *keyLength = entry->keyLength;
    *value = &entry->value;
    
    entrySize = getEntrySize(entry->keyLength);
    it->arenaOffset += entrySize;
    
    return true;
}
