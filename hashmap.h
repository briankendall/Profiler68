#ifndef HASHMAP_H
#define HASHMAP_H

#include <Types.h>

typedef enum HashtableStatus_ {
    kHashtableBadArgsError = -1,
    kHashtableNotEnoughMemoryError = -2,
    kHashtableNoErr = 0,
    
    kHashtableFoundKey = 1,
    kHashtableInsertedKey = 2,
    
} HashtableStatus;

typedef struct HashTable {
    UInt32 bucketCount; // must be power of two
    UInt32 *buckets; // offsets into arena (0 = empty bucket)
    UInt8 *arena; // arena memory
    UInt32 arenaSize;
    UInt32 arenaUsed;
} HashTable;

typedef struct HashtableIterator {
    UInt32 arenaOffset;
} HashtableIterator;

HashtableStatus hashtableInit(HashTable *table, void *mem, UInt32 memMize, UInt32 bucketCount);
Boolean hashtableLookup(HashTable *table, const UInt8 *key, UInt16 keyLength, UInt32 **outValue);
HashtableStatus hashtableInsertOrLookup(HashTable *table, const UInt8 *key, UInt16 keyLength, UInt32 **outValue);
void hashtableIterInit(HashtableIterator *it);
Boolean hashtableIterNext(HashTable *table, HashtableIterator *it, const UInt8 **key, UInt16 *keyLength, UInt32 **value);

#endif