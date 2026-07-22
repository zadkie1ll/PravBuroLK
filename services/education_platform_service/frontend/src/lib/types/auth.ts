export interface LoginResponse {
    detail: string,
    user: UserInterface

}
export interface MeResponse {
    detail: string,
    user: UserInterface
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
    department: string,
    departments: { code: string, name: string }[],
    is_staff: boolean
}
