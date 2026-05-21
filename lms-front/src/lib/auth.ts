import type { LoginResponse, MeResponse, RegistrationResponse } from "./types/auth"
import { backend } from "./utils"

export async function RegistateUser(login: string, password: string, department:string):Promise<RegistrationResponse>{
const postData = {
    username: login,
    password: password,
    department: department
}
const response = await fetch(`${backend}/api/education/reg/`, {
    method:"POST",
    credentials: "include",
    headers:{
        'Content-Type':'application/x-www-form-urlencoded'
    },
    body:new URLSearchParams(postData)
})
const data = await response.json()
if(!response.ok){
    throw new Error(data.detail || "Ошибка регистрации")
}
return data as RegistrationResponse;
}
export async function GetInfoAboutMe():Promise<MeResponse>{
    const response = await fetch(`${backend}/api/education/auth/me/`, {
        credentials: "include",
    })
    if (!response.ok){
        throw new Error(String(response.status))
    }
    return response.json() as Promise<MeResponse>;
}
export async function LoginUser(login:string, password: string, department?: string){
    const postData = {
        username: login,
        password: password,
        ...(department ? { department } : {})
    }
    const response = await fetch(`${backend}/api/education/auth/`, {
    method:"POST",
    credentials: "include",
    headers:{
        'Content-Type':'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams(postData)
})
const data = await response.json()
if(!response.ok){
    throw new Error(data.detail || "Ошибка входа")
}
return data as LoginResponse;
}
