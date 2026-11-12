export type Role="admin"|"analyst"|"viewer";
export interface User{email:string;role:Role}
export interface Entity{id:string;created_at:string;[key:string]:any}
export interface Layer{stratum:string;N:number;D:number;estimated_rate:number;minimum:number|null;weight:number;quota?:number;detection_probability?:number;miss_probability?:number;guaranteed?:boolean}
export interface DocumentRow{position:number;document_id:string;lot_id:string;lot_name:string;stratum:string}
export type CheckResult="qualified"|"error";
export interface CheckEntry{document_id:string;result:CheckResult;source?:string;note?:string}
export interface ConflictEntry{source:string;result:CheckResult;note:string;created_at:string}
export interface Conflict{document_id:string;results:CheckResult[];sources:string[];entries:ConflictEntry[]}
export interface Coverage{
 manifest_total:number;checked_total:number;missing_total:number;error_total:number;
 conflict_total:number;conflicts:Conflict[];missing_document_ids:string[];
 error_document_ids:string[];adjudicated_document_ids:string[];
}
export interface MeasuredLayer{stratum:string;N:number;n:number;d:number;upper_95:number;observed_rate:number;error_rate_upper:number;confidence_level:number;estimated_D_assumption_only:number}
