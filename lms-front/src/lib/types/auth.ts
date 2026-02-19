export interface LoginResponse {
    detail: string,
    user: UserInterface

}
export interface MeResponse {
    fullname: string,
    role: string,
    department:string
}
export interface RegistrationResponse {
    detail: string,
    user: UserInterface
}
interface UserInterface {
    id: number, 
    username: string,
    first_name: string,
    last_name: string,
    department: string
}