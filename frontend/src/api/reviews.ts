import {request} from "./client";
export const fetchReviews=()=>request("/reviews");
export const createReviews=(body:unknown)=>request("/reviews","POST",body);
export const fetchCoverage=(id:string)=>request("/reviews/"+id+"/coverage");
export const mergeChecks=(id:string,body:unknown)=>request("/reviews/"+id+"/checks","POST",body);
export const resolveConflict=(id:string,body:unknown)=>request("/reviews/"+id+"/conflicts/resolve","POST",body);
export const approveReview=(id:string)=>request("/reviews/"+id+"/approve","POST");
