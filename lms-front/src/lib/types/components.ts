export interface Course {
    id: number,
    name: string,
    photo_url:string,
    description: string,
    image_url: string,
    modules_count: number,
    completed_modules?: number;
}
export interface Module {
    id: number,
    name: string,
    description: string,
    video_url: string,
    order: number,
    status: string
}