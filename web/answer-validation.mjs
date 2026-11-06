// Matches the desktop's advisory INN checksum check; no registration lookup.
export function validInn(value) {
  if (!/^(?:[0-9]{10}|[0-9]{12})$/.test(value)) return false;
  const digits=[...value].map(Number);
  const check=weights=>weights.reduce((sum,w,i)=>sum+w*digits[i],0)%11%10;
  return value.length===10
    ? check([2,4,10,3,5,9,4,6,8])===digits[9]
    : check([7,2,4,10,3,5,9,4,6,8])===digits[10]&&check([3,7,2,4,10,3,5,9,4,6,8])===digits[11];
}
