/*
	ExtnGlue.i

	Copyright (C) 2006 Paul C. Pratt

	You can redistribute this file and/or modify it under the terms
	of version 2 of the GNU General Public License as published by
	the Free Software Foundation.  You should have received a copy
	of the license along with this file; see the file COPYING.

	This file is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	license for more details.
*/

#define kCallCheckValFails (-1)


#define SonyVarsPtr 0x0134

#define kcom_checkval 0x841339E2
#define kcom_callcheck 0x5B17

struct MyDriverDat_R {
	ui5b zeroes[4];
	ui5b checkval;
	ui5b pokeaddr;
};
typedef struct MyDriverDat_R MyDriverDat_R;

#ifndef UseParamBuffersExtension
#define UseParamBuffersExtension 0
#endif

#ifndef UseDiskDriverExtension
#define UseDiskDriverExtension 0
#endif

#ifndef UseHostClipExchangeExtension
#define UseHostClipExchangeExtension 0
#endif

#define kFindExtnExtension 0x64E1F58A
#define kDiskDriverExtension 0x4C9219E6
#define kHostParamBuffersExtension 0x314C87BF
#define kHostClipExchangeExtension 0x27B130CA

#define DSKDat_checkval 0
#define DSKDat_extension 2
#define DSKDat_commnd 4
#define DSKDat_result 6
#define DSKDat_params 8
#define DSKDat_TotSize 32

#define kCmndVersion 0

#define kCmndFindExtnFind 1
#define kCmndFindExtnId2Code 2
#define kCmndFindExtnCount 3

#define kParamVersion 8

#define kParamFindExtnTheExtn 8
#define kParamFindExtnTheId 12

#define kParamDiskNumDrives 8
#define kParamDiskStart 8
#define kParamDiskCount 12
#define kParamDiskBuffer 16
#define kParamDiskDrive_No 20


#define get_long(x) (*((ui5b *)(x)))
#define get_word(x) (*((ui4b *)(x)))
#define get_byte(x) (*((ui3b *)(x)))
#define put_long(x, v) (*((ui5b *)(x))) = ((ui5b)(v))
#define put_word(x, v) (*((ui4b *)(x))) = ((ui4b)(v))
#define put_byte(x, v) (*((ui3b *)(x))) = ((ui3b)(v))

struct XtnsDR {
	ui5b pokeaddr;

#if UseDiskDriverExtension
	ui4b DiskExtnId;
#endif

#if UseParamBuffersExtension
	ui4b PBufExtnId;
#endif

#if UseHostClipExchangeExtension
	ui4b HTCExtnId;
#endif
};
typedef struct XtnsDR XtnsDR;

static void InvokeExtension(ui5b pokeaddr, ui5b datp)
/*
	make seperate function to prevent
	invalid compiler optimations
*/
{
	put_long(pokeaddr, datp);
}

static OSErr InvokeExtension2(XtnsDR *xd, ui3b *datp)
{
	OSErr err;

	put_word(datp + DSKDat_checkval, kcom_callcheck);
	InvokeExtension(xd->pokeaddr, (ui5b)datp);
	if (get_word(datp + DSKDat_checkval) != 0) {
		err = (OSErr)kCallCheckValFails;
	} else {
		err = get_word(datp + DSKDat_result);
	}

	return err;
}

static void FindExtension(XtnsDR *xd,
	ui5b TheExtension, ui4b *id, OSErr *CombinedErr)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_extension, 0);
	put_word(DskDatV + DSKDat_commnd, kCmndFindExtnFind);
	put_long(DskDatV + kParamFindExtnTheExtn, TheExtension);

	err = InvokeExtension2(xd, DskDatV);
	if (noErr != err) {
		*id = (ui4b) -1;
		if (noErr != *CombinedErr) {
			*CombinedErr = err;
		}
	} else {
		*id = get_word(DskDatV + kParamFindExtnTheId);
	}
}

static OSErr InitExtensions(XtnsDR *xd)
{
	MyDriverDat_R *SonyVars;
	OSErr err = -1;

	SonyVars = (MyDriverDat_R *)get_long(SonyVarsPtr);

	if ((SonyVars == NULL)
		|| (SonyVars->zeroes[0] != 0)
		|| (SonyVars->zeroes[1] != 0)
		|| (SonyVars->zeroes[2] != 0)
		/* || (SonyVars->zeroes[3] != 0) */
		|| (SonyVars->checkval != kcom_checkval)
		)
	{
		/* fprintf(stderr, "no Mini vMac extension mechanism\n"); */
	} else {
		xd->pokeaddr = SonyVars->pokeaddr;

		if (xd->pokeaddr == 0) {
			/* fprintf(stderr, "pokeaddr == 0, no Mini vMac extension mechanism\n"); */
		} else {
			err = (OSErr)noErr;

#if UseParamBuffersExtension
			FindExtension(xd, kHostParamBuffersExtension,
				&xd->PBufExtnId, &err);
#endif
#if UseDiskDriverExtension
			FindExtension(xd, kDiskDriverExtension,
				&xd->DiskExtnId, &err);
#endif
#if UseHostClipExchangeExtension
			FindExtension(xd, kHostClipExchangeExtension,
				&xd->HTCExtnId, &err);
#endif
		}
	}

	return err;
}


#if UseParamBuffersExtension

#define kCmndPbufFeatures 1
#define kCmndPbufNew 2
#define kCmndPbufDispose 3
#define kCmndPbufGetSize 4
#define kCmndPbufTransfer 5

static OSErr InvokePBufExtension(XtnsDR *xd, ui3b *datp)
{
	put_word(datp + DSKDat_extension, xd->PBufExtnId);
	return InvokeExtension2(xd, datp);
}

#define NotAPbuf ((ui4b)0xFFFF)

static OSErr PbufVersion(XtnsDR *xd, ui4b *version)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndVersion);
	err = InvokePBufExtension(xd, DskDatV);
	if (noErr == err) {
		*version = get_word(DskDatV + kParamVersion);
	}
	return err;
}

static OSErr PbufFeatures(XtnsDR *xd, ui5b *features)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndPbufFeatures);
	err = InvokePBufExtension(xd, DskDatV);
	*features = get_long(DskDatV + DSKDat_params + 0);
	return err;
}

static OSErr PbufNew(XtnsDR *xd, ui5b count, ui4b *r)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */
	put_long(DskDatV + DSKDat_params + 4, count);

	put_word(DskDatV + DSKDat_commnd, kCmndPbufNew);
	err = InvokePBufExtension(xd, DskDatV);
	*r = get_word(DskDatV + DSKDat_params + 0);
	return err;
}

static OSErr PbufDispose(XtnsDR *xd, ui4b i)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + DSKDat_params + 0, i);
	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */

	put_word(DskDatV + DSKDat_commnd, kCmndPbufDispose);
	return InvokePBufExtension(xd, DskDatV);
}

static OSErr PBufGetSize(XtnsDR *xd,
	ui4b i, ui5b *count)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_params + 0, i);
	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */

	put_word(DskDatV + DSKDat_commnd, kCmndPbufGetSize);
	err = InvokePBufExtension(xd, DskDatV);
	*count = get_long(DskDatV + DSKDat_params + 4);
	return err;
}

static OSErr PbufTransfer(XtnsDR *xd, void *Buffer,
	ui4b i, ui5b offset, ui5b count, blnr IsWrite)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + DSKDat_params + 0, i);
	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */
	put_long(DskDatV + DSKDat_params + 4, offset);
	put_long(DskDatV + DSKDat_params + 8, count);
	put_long(DskDatV + DSKDat_params + 12, Buffer);
	put_word(DskDatV + DSKDat_params + 16, IsWrite ? 1 : 0);

	put_word(DskDatV + DSKDat_commnd, kCmndPbufTransfer);
	return InvokePBufExtension(xd, DskDatV);
}

#endif /* UseParamBuffersExtension */


#if UseDiskDriverExtension

#define kCmndDiskNDrives 1
#define kCmndDiskRead 2
#define kCmndDiskWrite 3
#define kCmndDiskEject 4
#define kCmndDiskGetSize 5
#define kCmndDiskGetCallBack 6
#define kCmndDiskSetCallBack 7
#define kCmndDiskQuitOnEject 8
#define kCmndDiskFeatures 9
#define kCmndDiskNextPendingInsert 10
#define kCmndDiskGetRawMode 11
#define kCmndDiskSetRawMode 12
#define kCmndDiskNew 13
#define kCmndDiskGetNewWanted 14
#define kCmndDiskEjectDelete 15
#define kCmndDiskGetName 16

static OSErr InvokeDiskExtension(XtnsDR *xd, ui3b *datp)
{
	put_word(datp + DSKDat_extension, xd->DiskExtnId);
	return InvokeExtension2(xd, datp);
}

static OSErr DiskVersion(XtnsDR *xd, ui4b *version)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndVersion);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*version = get_word(DskDatV + kParamVersion);
	}
	return err;
}

#define kFeatureCmndDisk_RawMode 0
#define kFeatureCmndDisk_New 1
#define kFeatureCmndDisk_NewName 2
#define kFeatureCmndDisk_GetName 3

static OSErr DiskFeatures(XtnsDR *xd, ui5b *features)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndDiskFeatures);
	err = InvokeDiskExtension(xd, DskDatV);
	*features = get_long(DskDatV + DSKDat_params + 0);
	return err;
}

static OSErr DiskRead(XtnsDR *xd,
	void *Buffer, ui4b Drive_No,
	ui5b Sony_Start, ui5b *Sony_Count)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_long(DskDatV + kParamDiskStart, Sony_Start);
	put_long(DskDatV + kParamDiskCount, *Sony_Count);
	put_long(DskDatV + kParamDiskBuffer, (long)Buffer);
	put_word(DskDatV + kParamDiskDrive_No, Drive_No);
	put_word(DskDatV + DSKDat_commnd, kCmndDiskRead);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*Sony_Count = get_long(DskDatV + kParamDiskCount);
	}
	return err;
}

static OSErr DiskWrite(XtnsDR *xd,
	void *Buffer, ui4b Drive_No,
	ui5b Sony_Start, ui5b *Sony_Count)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_long(DskDatV + kParamDiskStart, Sony_Start);
	put_long(DskDatV + kParamDiskCount, *Sony_Count);
	put_long(DskDatV + kParamDiskBuffer, (long)Buffer);
	put_word(DskDatV + kParamDiskDrive_No, Drive_No);
	put_word(DskDatV + DSKDat_commnd, kCmndDiskWrite);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*Sony_Count = get_long(DskDatV + kParamDiskCount);
	}
	return err;
}

static OSErr DiskEject(XtnsDR *xd, ui4b Drive_No)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + kParamDiskDrive_No, Drive_No);
	put_word(DskDatV + DSKDat_commnd, kCmndDiskEject);
	return InvokeDiskExtension(xd, DskDatV);
}

static OSErr DiskGetSize(XtnsDR *xd,
	ui4b Drive_No, ui5b *Sony_Count)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + kParamDiskDrive_No, Drive_No);
	put_word(DskDatV + DSKDat_commnd, kCmndDiskGetSize);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*Sony_Count = get_long(DskDatV + kParamDiskCount);
	}
	return err;
}

static OSErr DiskGetCallBack(XtnsDR *xd, ui5b *p)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndDiskGetCallBack);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*p = get_long(DskDatV + kParamDiskBuffer);
	}
	return err;
}

static OSErr DiskSetCallBack(XtnsDR *xd, ui5b p)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + DSKDat_commnd, kCmndDiskSetCallBack);
	put_long(DskDatV + kParamDiskBuffer, p);
	return InvokeDiskExtension(xd, DskDatV);
}

static OSErr DiskGetRawMode(XtnsDR *xd, ui4b *m)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndDiskGetRawMode);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*m = get_word(DskDatV + kParamDiskBuffer);
	}
	return err;
}

static OSErr DiskSetRawMode(XtnsDR *xd, ui4b m)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + DSKDat_commnd, kCmndDiskSetRawMode);
	put_word(DskDatV + kParamDiskBuffer, m);
	return InvokeDiskExtension(xd, DskDatV);
}

static OSErr DiskNextPendingInsert(XtnsDR *xd, ui4b *Drive_No)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndDiskNextPendingInsert);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*Drive_No = get_word(DskDatV + kParamDiskDrive_No);
	}
	return err;
}

static OSErr DiskNew(XtnsDR *xd, ui5b L, ui4b Name)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_long(DskDatV + DSKDat_params + 0, L);
	put_word(DskDatV + DSKDat_params + 4, Name);
	put_word(DskDatV + DSKDat_params + 6, 0); /* reserved */
	put_word(DskDatV + DSKDat_commnd, kCmndDiskNew);
	return InvokeDiskExtension(xd, DskDatV);
}

static OSErr DiskGetNewWanted(XtnsDR *xd, ui4b *m)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndDiskGetNewWanted);
	err = InvokeDiskExtension(xd, DskDatV);
	if (noErr == err) {
		*m = get_word(DskDatV + kParamDiskBuffer);
	}
	return err;
}

static OSErr DiskGetName(XtnsDR *xd,
	ui4b Drive_No, ui4b *r)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_params + 0, Drive_No);
	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */

	put_word(DskDatV + DSKDat_commnd, kCmndDiskGetName);
	err = InvokeDiskExtension(xd, DskDatV);
	*r = get_word(DskDatV + DSKDat_params + 4);
	return err;
}

static OSErr DiskEjectDelete(XtnsDR *xd, ui4b Drive_No)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + kParamDiskDrive_No, Drive_No);
	put_word(DskDatV + DSKDat_commnd, kCmndDiskEjectDelete);
	return InvokeDiskExtension(xd, DskDatV);
}

#endif /* UseDiskDriverExtension */


#if UseHostClipExchangeExtension

#define kCmndHTCEFeatures 1
#define kCmndHTCEExport 2
#define kCmndHTCEImport 3

static OSErr InvokeHTCExtension(XtnsDR *xd, ui3b *datp)
{
	put_word(datp + DSKDat_extension, xd->HTCExtnId);
	return InvokeExtension2(xd, datp);
}

static OSErr HTCVersion(XtnsDR *xd, ui4b *version)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndVersion);
	err = InvokeHTCExtension(xd, DskDatV);
	*version = get_word(DskDatV + kParamVersion);
	return err;
}

static OSErr HTCFeatures(XtnsDR *xd, ui5b *features)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_commnd, kCmndHTCEFeatures);
	err = InvokeHTCExtension(xd, DskDatV);
	*features = get_long(DskDatV + DSKDat_params + 0);
	return err;
}

static OSErr HTCImport(XtnsDR *xd, ui4b *r)
{
	ui3b DskDatV[DSKDat_TotSize];
	OSErr err;

	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */

	put_word(DskDatV + DSKDat_commnd, kCmndHTCEImport);
	err = InvokeHTCExtension(xd, DskDatV);
	*r = get_word(DskDatV + DSKDat_params + 0);
	return err;
}

static OSErr HTCExport(XtnsDR *xd, ui4b i)
{
	ui3b DskDatV[DSKDat_TotSize];

	put_word(DskDatV + DSKDat_params + 0, i);
	put_word(DskDatV + DSKDat_params + 2, 0); /* reserved */

	put_word(DskDatV + DSKDat_commnd, kCmndHTCEExport);
	return InvokeHTCExtension(xd, DskDatV);
}

#endif /* UseHostClipExchangeExtension */
